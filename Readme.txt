INTRODUCTION
------------
This is a plugin for Blender. It handles import and export of the MDC file
format. The MDC file format is a 3D model format used in games such as
Return to Castle Wolfenstein or Wolfenstein: Enemy Territory. Support ranges
from Blender version 2.69 to 2.79, other versions may work too.

ABOUT USING THIS PLUGIN
-----------------------

https://youtu.be/ghj8sMLTUf0

ABOUT CODE
----------
The code emphasizes readability. Therefore there are many comments and the
style is more Java-oriented. It may also be unoptimized in order to prevent
having it be totally unreadable.

The main guts of this code lies in the modules "mdc_file.py" and
"blender_scene.py". The converter.py module sits between both and converts
the data between both modules. This is for decoupling reasons.