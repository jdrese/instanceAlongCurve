
![Screenshot](screenshot.png)
Instance Along Curve
==================

### About
Maya Plugin for interactive instancing of shapes along curves.

### Features
![Features1](iac_1.gif)

### Installation

Save instanceAlongCurve.py under MAYA_PLUG_IN_PATH, which in Windows usually is C:\Users\<username>\Documents\maya\<version>\plug-ins

### Use
To use the plugin, select a curve and the shape you want to instance and go to Edit->Instance Along Curve. You can save it as a Shelf Button if you want.


### Documentation

In progress.

#### Known issues
* When batch rendering, if the node has complex logic depending on time, it may be necessary to bake the node and its children. In some renderers, the node is not being evaluated each frame.
