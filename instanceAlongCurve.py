import sys
import pymel.core as pm
import maya.OpenMayaMPx as OpenMayaMPx
import maya.OpenMaya as OpenMaya
import maya.OpenMayaRender as OpenMayaRender

kPluginCmdName = "instanceAlongCurve"
kPluginNodeName = 'instanceAlongCurveLocator'
kPluginNodeClassify = 'utility/general'
kPluginNodeId = OpenMaya.MTypeId( 0x55555 ) 

glRenderer = OpenMayaRender.MHardwareRenderer.theRenderer()
glFT = glRenderer.glFunctionTable()

# Ideas:
#   - three orientation modes: no orientation, tangent, normal
#   - orientation constraints: set a fixed axis?

class instanceAlongCurveLocator(OpenMayaMPx.MPxLocatorNode):

    # Input attr
    inputCurveAttr = OpenMaya.MObject()
    inputTransformAttr = OpenMaya.MObject()

    instanceCountAttr = OpenMaya.MObject()
    instancingModeAttr = OpenMaya.MObject()
    instanceLengthAttr = OpenMaya.MObject()
    maxInstancesByLengthAttr = OpenMaya.MObject()

    knownInstancesAttr = OpenMaya.MObject()
    displayTypeAttr = OpenMaya.MObject()
    bboxAttr = OpenMaya.MObject()

    # Output sentinel attr
    sentinelAttr = OpenMaya.MObject()

    def __init__(self):
        self.triggerUpdate = False
        OpenMayaMPx.MPxLocatorNode.__init__(self)

    def postConstructor(self):
        OpenMaya.MFnDependencyNode(self.thisMObject()).setName("instanceAlongCurveLocatorShape#")

    # Helper function to get an array of available logical indices from the sparse array
    def getAvailableLogicalIndices(self, plug, numIndices):
        
        # Allocate and initialize
        outIndices = OpenMaya.MIntArray(numIndices)
        indices = OpenMaya.MIntArray(plug.numElements())
        plug.getExistingArrayAttributeIndices(indices)

        currentAvailableIndex = 0
        indicesFound = 0

        # Assuming indices are SORTED :)
        for i in indices:

            connectedPlug = plug.elementByLogicalIndex(i).isConnected()

            # Iteratively find available indices in the sparse array
            while i > currentAvailableIndex:
                outIndices[indicesFound] = currentAvailableIndex
                indicesFound += 1
                currentAvailableIndex += 1

            # Check against this index, add it if it is not connected
            if i == currentAvailableIndex and not connectedPlug:
                outIndices[indicesFound] = currentAvailableIndex
                indicesFound += 1

            currentAvailableIndex += 1

            if indicesFound == numIndices:
                return outIndices

        # Fill remaining expected indices
        for i in xrange(indicesFound, numIndices):
            outIndices[i] = currentAvailableIndex
            currentAvailableIndex += 1

        return outIndices

    # Find original SG to reassign it to instance
    def getSG(self, dagPath):

        dagPath.extendToShape()
        fnDepNode = OpenMaya.MFnDependencyNode(dagPath.node())
        depNode = dagPath.node()

        instObjGroupsAttr = fnDepNode.attribute('instObjGroups')      
        instPlugArray = OpenMaya.MPlug(depNode, instObjGroupsAttr)
        instPlugArrayElem = instPlugArray.elementByLogicalIndex(dagPath.instanceNumber())

        if instPlugArrayElem.isConnected():
            
            connectedPlugs = OpenMaya.MPlugArray()      
            instPlugArrayElem.connectedTo(connectedPlugs, False, True)

            if connectedPlugs.length() == 1:

                sgNode = connectedPlugs[0].node()

                if(sgNode.hasFn(OpenMaya.MFn.kSet)):
                    return OpenMaya.MFnSet(sgNode)

        # No SG found, just return an empty one
        return OpenMaya.MFnSet()

    def updateDrawingOverrides(self):
        knownInstancesPlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.knownInstancesAttr)
        drawMode = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.displayTypeAttr).asInt()
        useBBox = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.bboxAttr).asBool()

        connections = OpenMaya.MPlugArray()

        for i in xrange(knownInstancesPlug.numConnectedElements()):

            knownPlugElement = knownInstancesPlug.elementByPhysicalIndex(i)
            knownPlugElement.connectedTo(connections, True, False)
            
            for c in xrange(0, connections.length()):
                instanceFn = OpenMaya.MFnTransform(connections[c].node())
                self.setDrawingOverride(instanceFn, drawMode, useBBox)

    def setDrawingOverride(self, nodeFn, drawMode, useBBox):
        overrideEnabledPlug = nodeFn.findPlug("overrideEnabled", False)
        overrideEnabledPlug.setBool(True)

        displayPlug = nodeFn.findPlug("overrideDisplayType", False)
        displayPlug.setInt(drawMode)

        lodPlug = nodeFn.findPlug("overrideLevelOfDetail", False)
        lodPlug.setInt(useBBox)

    def getCurveFn(self, curvePlug):

        if curvePlug.isConnected():
            connections = OpenMaya.MPlugArray()
            curvePlug.connectedTo(connections, True, False)
            
            if connections.length() == 1:

                # Get Fn from a DAG path to get the world transformations correctly
                path = OpenMaya.MDagPath()

                trFn = OpenMaya.MFnDagNode(connections[0].node())
                trFn.getPath(path)

                path.extendToShape()

                return OpenMaya.MFnNurbsCurve(path)

        return OpenMaya.MFnNurbsCurve()

    def draw(self, view, path, style, status):

        self.updateInstanceConnections(path)

        # Draw simple locator lines
        view.beginGL()
 
        glFT.glBegin(OpenMayaRender.MGL_LINES)
        glFT.glVertex3f(0.0, -0.5, 0.0)
        glFT.glVertex3f(0.0, 0.5, 0.0)
        
        glFT.glVertex3f(0.5, 0.0, 0.0)
        glFT.glVertex3f(-0.5, 0.0, 0.0)

        glFT.glVertex3f(0.0, 0.0, 0.5)
        glFT.glVertex3f(0.0, 0.0, -0.5)      
        glFT.glEnd()
 
        view.endGL()

    # Calculate expected instances by the instancing mode
    def getInstanceCountByMode(self):
        instancingModePlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.instancingModeAttr)
        inputCurvePlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.inputCurveAttr)

        if inputCurvePlug.isConnected() and instancingModePlug.asInt() == 1:
            instanceLengthPlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.instanceLengthAttr)
            maxInstancesByLengthPlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.maxInstancesByLengthAttr)
            curveFn = self.getCurveFn(inputCurvePlug)
            return min(maxInstancesByLengthPlug.asInt(), int(curveFn.length() / instanceLengthPlug.asFloat()))

        instanceCountPlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.instanceCountAttr)
        return instanceCountPlug.asInt()

    def updateInstanceConnections(self, path):
        expectedInstanceCount = self.getInstanceCountByMode()
        knownInstancesPlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.knownInstancesAttr)

        self.forceCompute()

        # Only instance if we are missing elements
        if knownInstancesPlug.numConnectedElements() < expectedInstanceCount:

            inputTransformPlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.inputTransformAttr)

            # Get connected input transform plugs 
            inputTransformConnectedPlugs = OpenMaya.MPlugArray()
            inputTransformPlug.connectedTo(inputTransformConnectedPlugs, True, False)

            # Find input transform
            if inputTransformConnectedPlugs.length() == 1:
                transform = inputTransformConnectedPlugs[0].node()
                transformFn = OpenMaya.MFnTransform(transform)

                drawMode = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.displayTypeAttr).asInt()
                useBBox = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.bboxAttr).asBool()
                self.triggerUpdate = True

                # Get shading group first
                dagPath = OpenMaya.MDagPath()
                transformFn.getPath(dagPath)
                shadingGroupFn = self.getSG(dagPath)

                mdgModifier = OpenMaya.MDGModifier()

                instanceCount = expectedInstanceCount - knownInstancesPlug.numConnectedElements()
                availableIndices = self.getAvailableLogicalIndices(knownInstancesPlug, instanceCount)

                nodeFn = OpenMaya.MFnDagNode(path.transform())

                # Instance as many times as necessary
                for i in availableIndices:
                    
                    # Instance transform and reassign SG
                    trInstance = transformFn.duplicate(True, True)

                    # Parent new instance
                    nodeFn.addChild(trInstance)

                    # TODO: Handle inexistant SG
                    shadingGroupFn.addMember(trInstance)

                    instanceFn = OpenMaya.MFnTransform(trInstance)
                    self.setDrawingOverride(instanceFn, drawMode, useBBox)

                    instObjGroupsAttr = instanceFn.attribute('message')
                    instPlugArray = OpenMaya.MPlug(trInstance, instObjGroupsAttr)
                    
                    knownInstancesPlugElement = knownInstancesPlug.elementByLogicalIndex(i)
                    mdgModifier.connect(instPlugArray, knownInstancesPlugElement)

                mdgModifier.doIt()

        # Remove instances if necessary
        elif knownInstancesPlug.numConnectedElements() > expectedInstanceCount:
            self.triggerUpdate = True

            mdgModifier = OpenMaya.MDGModifier()
            connections = OpenMaya.MPlugArray()
            
            numConnectedElements = knownInstancesPlug.numConnectedElements()
            toRemove = knownInstancesPlug.numConnectedElements() - expectedInstanceCount

            for i in xrange(toRemove):

                knownPlugElement = knownInstancesPlug.connectionByPhysicalIndex(numConnectedElements - 1 - i)
                knownPlugElement.connectedTo(connections, True, False)
                
                for c in xrange(connections.length()):
                    node = connections[c].node()
                    mdgModifier.disconnect(connections[c], knownPlugElement)
                    mdgModifier.deleteNode(node)

            mdgModifier.doIt()

        # Update is done in the draw method to prevent being flooded with modifications from the curve callback
        if self.triggerUpdate:
            self.updateInstancePositions()

        self.triggerUpdate = False

        return OpenMaya.kUnknownParameter

    def updateInstancePositions(self):

        knownInstancesPlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.knownInstancesAttr)
        inputCurvePlug = OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.inputCurveAttr)

        if inputCurvePlug.isConnected():

            fnCurve = self.getCurveFn(inputCurvePlug)
            curveLength = fnCurve.length()

            numConnectedElements = knownInstancesPlug.numConnectedElements()
            point = OpenMaya.MPoint()
            connections = OpenMaya.MPlugArray()          

            # TODO: let the user decide forward axis?
            startOrientation = OpenMaya.MVector(0.0, 0.0, 1.0)
            curvePointIndex = 0

            for i in xrange(numConnectedElements):

                param = fnCurve.findParamFromLength(curveLength * (float(curvePointIndex) / numConnectedElements))
                fnCurve.getPointAtParam(param, point, OpenMaya.MSpace.kWorld)
                tangent = fnCurve.tangent(param, OpenMaya.MSpace.kWorld)
                rot = startOrientation.rotateTo(tangent)

                curvePointIndex += 1

                knownPlugElement = knownInstancesPlug.elementByPhysicalIndex(i)
                knownPlugElement.connectedTo(connections, True, False)
                
                for c in xrange(0, connections.length()):
                    instanceFn = OpenMaya.MFnTransform(connections[c].node())
                    instanceFn.setTranslation(OpenMaya.MVector(point), OpenMaya.MSpace.kTransform)
                    instanceFn.setRotation(rot)

    # Remember to remove callbacks on disconnection
    def connectionBroken(self, plug, otherPlug, asSrc):
        if plug.attribute() == instanceAlongCurveLocator.inputCurveAttr:
            OpenMaya.MMessage.removeCallback(self.curveTransformCallback)
            OpenMaya.MMessage.removeCallback(self.curveCallback)

        return OpenMaya.kUnknownParameter

    # Get notified when curve shape and transform is modified
    def connectionMade(self, plug, otherPlug, asSrc):
        if plug.attribute() == instanceAlongCurveLocator.inputCurveAttr:

            dagPath = OpenMaya.MDagPath()

            trDagNode = OpenMaya.MFnDagNode(otherPlug.node())
            trDagNode.getPath(dagPath)

            dagPath.extendToShape()

            # Get callbacks for shape and transform modifications
            self.curveTransformCallback = OpenMaya.MNodeMessage.addNodeDirtyPlugCallback(otherPlug.node(), curveChangedCallback, self)
            self.curveCallback = OpenMaya.MNodeMessage.addNodeDirtyPlugCallback(dagPath.node(), curveChangedCallback, self)

            # Update instantly
            self.triggerUpdate = True
        
        return OpenMaya.kUnknownParameter

    # Compute method just for updating current instances display attributes
    def compute(self, plug, dataBlock):

        if plug == instanceAlongCurveLocator.sentinelAttr:
            self.updateDrawingOverrides()
            dataBlock.setClean(instanceAlongCurveLocator.sentinelAttr)

        return OpenMaya.kUnknownParameter

    # Query the sentinel value to force an evaluation
    def forceCompute(self):
        OpenMaya.MPlug(self.thisMObject(), instanceAlongCurveLocator.sentinelAttr).asInt()

    @staticmethod
    def nodeCreator():
        return OpenMayaMPx.asMPxPtr( instanceAlongCurveLocator() )

    @staticmethod
    def nodeInitializer():

        nAttr = OpenMaya.MFnNumericAttribute()
        msgAttributeFn = OpenMaya.MFnMessageAttribute()
        curveAttributeFn = OpenMaya.MFnTypedAttribute()
        enumFn = OpenMaya.MFnEnumAttribute()
        modeEnumFn = OpenMaya.MFnEnumAttribute()

        instanceAlongCurveLocator.inputTransformAttr = msgAttributeFn.create("inputTransform", "it")
        msgAttributeFn.setWritable( True )
        msgAttributeFn.setStorable( True )
        msgAttributeFn.setHidden( False )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.inputTransformAttr )

        instanceAlongCurveLocator.knownInstancesAttr = msgAttributeFn.create("knownInstances", "ki")
        msgAttributeFn.setWritable( True )
        msgAttributeFn.setStorable( True )    
        msgAttributeFn.setHidden( True )  
        msgAttributeFn.setArray( True )  
        msgAttributeFn.setDisconnectBehavior(OpenMaya.MFnAttribute.kDelete) # Very important :)
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.knownInstancesAttr )
        
        ## Input instance count    
        instanceAlongCurveLocator.instanceCountAttr = nAttr.create("instanceCount", "iic", OpenMaya.MFnNumericData.kInt, 5)
        nAttr.setMin(0)
        nAttr.setSoftMax(100)
        nAttr.setWritable( True )
        nAttr.setStorable( True )
        nAttr.setHidden( False )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.instanceCountAttr)

        ## Max instances when defined by instance length
        instanceAlongCurveLocator.maxInstancesByLengthAttr = nAttr.create("maxInstancesByLength", "mibl", OpenMaya.MFnNumericData.kInt, 50)
        nAttr.setMin(0)
        nAttr.setSoftMax(200)
        nAttr.setWritable( True )
        nAttr.setStorable( True )
        nAttr.setHidden( False )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.maxInstancesByLengthAttr)

        # Length between instances
        instanceAlongCurveLocator.instanceLengthAttr = nAttr.create("instanceLength", "ilength", OpenMaya.MFnNumericData.kFloat, 1.0)
        nAttr.setMin(0.01)
        nAttr.setSoftMax(10)
        nAttr.setWritable( True )
        nAttr.setStorable( True )
        nAttr.setHidden( False )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.instanceLengthAttr)
        
        # Input curve transform
        instanceAlongCurveLocator.inputCurveAttr = msgAttributeFn.create( 'inputCurve', 'curve')
        msgAttributeFn.setWritable( True )
        msgAttributeFn.setStorable( True ) 
        msgAttributeFn.setHidden( False )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.inputCurveAttr )

        # Display override options
        instanceAlongCurveLocator.displayTypeAttr = enumFn.create('instanceDisplayType', 'idt')
        enumFn.addField( "Normal", 0 );
        enumFn.addField( "Template", 1 );
        enumFn.addField( "Reference", 2 );
        enumFn.setDefault("Reference")
        enumFn.setWritable( True )
        enumFn.setStorable( True )
        enumFn.setHidden( False )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.displayTypeAttr )

        # Enum for selection of instancing mode
        instanceAlongCurveLocator.instancingModeAttr = modeEnumFn.create('instancingMode', 'instancingMode')
        modeEnumFn.addField( "Count", 0 );
        modeEnumFn.addField( "Distance", 1 );
        modeEnumFn.setWritable( True )
        modeEnumFn.setStorable( True )
        modeEnumFn.setHidden( False )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.instancingModeAttr )

        instanceAlongCurveLocator.bboxAttr = nAttr.create('instanceBoundingBox', 'ibb', OpenMaya.MFnNumericData.kBoolean, False)
        nAttr.setWritable( True )
        nAttr.setStorable( True )
        nAttr.setHidden( False )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.bboxAttr )

        instanceAlongCurveLocator.sentinelAttr = nAttr.create('sentinel', 's', OpenMaya.MFnNumericData.kInt, 0)
        nAttr.setWritable( False )
        nAttr.setStorable( False )
        nAttr.setReadable( True )
        nAttr.setHidden( True )
        instanceAlongCurveLocator.addAttribute( instanceAlongCurveLocator.sentinelAttr )

        instanceAlongCurveLocator.attributeAffects( instanceAlongCurveLocator.displayTypeAttr, instanceAlongCurveLocator.sentinelAttr )
        instanceAlongCurveLocator.attributeAffects( instanceAlongCurveLocator.bboxAttr, instanceAlongCurveLocator.sentinelAttr )

def curveChangedCallback(node, plug, self):
    self.triggerUpdate = True

def initializePlugin( mobject ):
    mplugin = OpenMayaMPx.MFnPlugin( mobject )
    try:
        # Register command
        # TODO: addmenuItem
        mplugin.registerCommand( kPluginCmdName, instanceAlongCurveCommand.cmdCreator )

        mplugin.addMenuItem("Instance Along Curve", "MayaWindow|mainEditMenu", kPluginCmdName, "")

        # Register AE template
        pm.callbacks(addCallback=loadAETemplateCallback, hook='AETemplateCustomContent', owner=kPluginNodeName)

        # Register node
        mplugin.registerNode( kPluginNodeName, kPluginNodeId, instanceAlongCurveLocator.nodeCreator,
                              instanceAlongCurveLocator.nodeInitializer, OpenMayaMPx.MPxNode.kLocatorNode, kPluginNodeClassify )
    except:
        sys.stderr.write( 'Failed to register plugin instanceAlongCurve')
        raise
    
def uninitializePlugin( mobject ):
    mplugin = OpenMayaMPx.MFnPlugin( mobject )
    try:
        mplugin.deregisterCommand( kPluginCmdName )
        mplugin.deregisterNode( kPluginNodeId )
    except:
        sys.stderr.write( 'Failed to deregister plugin instanceAlongCurve')
        raise

###############
# AE TEMPLATE #
###############
def loadAETemplateCallback(nodeName):
    AEinstanceAlongCurveLocatorTemplate(nodeName)

class AEinstanceAlongCurveLocatorTemplate(pm.ui.AETemplate):

    def addControl(self, control, label=None, **kwargs):
        pm.ui.AETemplate.addControl(self, control, label=label, **kwargs)

    def beginLayout(self, name, collapse=True):
        pm.ui.AETemplate.beginLayout(self, name, collapse=collapse)

    def __init__(self, nodeName):
        pm.ui.AETemplate.__init__(self,nodeName)
        self.thisNode = None
        self.node = pm.PyNode(self.nodeName)

        if self.node.type() == kPluginNodeName:
            self.beginScrollLayout()
            self.beginLayout("Instance Along Curve Settings" ,collapse=0)

            self.addControl("instancingMode", label="Instancing Mode", changeCommand=self.onInstanceModeChanged)
            self.addControl("instanceCount", label="Count")
            self.addControl("instanceLength", label="Distance")
            self.addControl("maxInstancesByLength", label="Max Instances")
            
            self.addSeparator()
            
            self.addControl("instanceDisplayType", label="Instance Display Type")
            self.addControl("instanceBoundingBox", label="Use bounding box")
            
            self.addSeparator()
            
            self.addControl("inputCurve", label="Input curve")
            self.addControl("inputTransform", label="Input object")
            self.addExtraControls()

            self.endLayout()
            self.endScrollLayout()

    def onInstanceModeChanged(self, nodeName):
        if pm.PyNode(nodeName).type() == kPluginNodeName:
            nodeAttr = pm.PyNode(nodeName + ".instancingMode")
            mode = nodeAttr.get("instancingMode")
            self.dimControl(nodeName, "instanceLength", mode == 0)
            self.dimControl(nodeName, "maxInstancesByLength", mode == 0)
            self.dimControl(nodeName, "instanceCount", mode == 1)
            # TODO: dim everything if there is no curve or transform

# Command
class instanceAlongCurveCommand(OpenMayaMPx.MPxCommand):

    def __init__(self):
        OpenMayaMPx.MPxCommand.__init__(self)
        self.mUndo = []

    def isUndoable(self):
        return True

    def undoIt(self): 
        OpenMaya.MGlobal.displayInfo( "Undo: instanceAlongCurveCommand\n" )

        # Reversed for undo :)
        for m in reversed(self.mUndo):
            m.undoIt()

    def redoIt(self): 
        OpenMaya.MGlobal.displayInfo( "Redo: instanceAlongCurveCommand\n" )
        
        for m in self.mUndo:
            m.doIt()
        
    def doIt(self,argList):
            
        list = OpenMaya.MSelectionList()
        OpenMaya.MGlobal.getActiveSelectionList(list)

        if list.length() == 2:
            curveDagPath = OpenMaya.MDagPath()
            list.getDagPath(0, curveDagPath)
            curveDagPath.extendToShape()

            shapeDagPath = OpenMaya.MDagPath()
            list.getDagPath(1, shapeDagPath)           

            if(curveDagPath.node().hasFn(OpenMaya.MFn.kNurbsCurve)):

                # We need the curve transform
                curveTransformFn = OpenMaya.MFnDagNode(curveDagPath.transform())
                curveTransformPlug = curveTransformFn.findPlug("message", True)

                # We need the shape's transform too
                transformFn = OpenMaya.MFnDagNode(shapeDagPath.transform())
                transformMessagePlug = transformFn.findPlug("message", True)

                # Create node first
                mdagModifier = OpenMaya.MDagModifier()
                self.mUndo.append(mdagModifier)
                newNode = mdagModifier.createNode(kPluginNodeId)
                mdagModifier.doIt()

                # Assign new correct name and select new locator
                newNodeFn = OpenMaya.MFnDagNode(newNode)
                newNodeFn.setName("instanceAlongCurveLocator#")

                # Get the node shape
                nodeShapeDagPath = OpenMaya.MDagPath()
                newNodeFn.getPath(nodeShapeDagPath)
                nodeShapeDagPath.extendToShape()
                newNodeFn = OpenMaya.MFnDagNode(nodeShapeDagPath)

                OpenMaya.MGlobal.clearSelectionList()
                msel = OpenMaya.MSelectionList()
                msel.add(nodeShapeDagPath)
                OpenMaya.MGlobal.setActiveSelectionList(msel)

                # Connect :D
                mdgModifier = OpenMaya.MDGModifier()
                self.mUndo.append(mdgModifier)               
                mdgModifier.connect(curveTransformPlug, newNodeFn.findPlug(instanceAlongCurveLocator.inputCurveAttr))
                mdgModifier.connect(transformMessagePlug, newNodeFn.findPlug(instanceAlongCurveLocator.inputTransformAttr))
                mdgModifier.doIt()
                
            else:
                sys.stderr.write("Please select a curve first")
        else:
            sys.stderr.write("Please select a curve and a shape")

    @staticmethod
    def cmdCreator():
        return OpenMayaMPx.asMPxPtr( instanceAlongCurveCommand() )