INTRODUCTION
------------
This is a plugin for Blender. It handles import and export of the MDC file
format. The MDC file format is a 3D model format used in games such as
Return to Castle Wolfenstein or Wolfenstein: Enemy Territory. This plugin
is still in development (see the Note in the following section about the uv
maps). Apart from that it should already be usable.

ABOUT USING THIS PLUGIN
-----------------------
Place the contents of the directory called "io_scene_mdc" into Blender's
installation path under "addons". This folder may be different on each
platform. On Windows an example path is:

C:\Program Files\Blender Foundation\Blender\2.76\scripts\addons

After that you need to enable the Add-on. To do so, open up Blender, go to
"File -> User Preferences -> Add-ons". In there search for "mdc". Toggle the
checkbox to enable it and hit "Save User Settings" to save your settings. Now
option "RtCW/ET Model (.mdc)" should appear under "File -> Import" and
"File -> Export".

Finally, there are some options for import or export. For example to have
control over how vertex normals are imported, simply set the option in the
Combobox called 'Vertex Normals' in the import dialog.

Support for Blender ranges from version 2.69 to 2.79, other versions may work
too.

Note: that uv mapping is still an unfixed issue in this plugin. This means that
you need to make sure that each vertex in your model is mapped exactly once
to the uv map, only then will the uv map correctly be exported. Some future
versions of this script may include a fix for this so one can create nice uv
maps in Blender and export them to MDC.

ABOUT CODE
----------
The code emphasizes readability. Therefore there are many comments and the
style is more Java-oriented. It may also be unoptimized in order to prevent
having it be totally unreadable.

The main guts of this code lies in the modules "mdc_file.py" and
"blender_scene.py". The converter.py module sits between both and converts
the data between both modules. This is for decoupling reasons.

Tags are mapped as arrows. Vertex normals are mapped as single arrows.

MORE ABOUT MDC
--------------
The MDC file format is a successor format of the MD3 file format. It has the
same features as MD3, but differs in that it uses a bit more advanced
compression methods to save memory. Compression is quite easy to understand on
the vertex coordinates, but a little more complicated on the vertex normals.

The vertex coordinates are compressed by dividing frame space into compressed
frames and base frames. The base frames still work the same as in MD3, that
means absolute vertex coordinates are stored. Compressed frames on the other
hand store just relative values. The values are relative to its baseframe. The
final vertex coordinate then is simply a vector addition of the base frame and
the comp frame coordinates. This saves memory, as the relative vertex
coordinates can be stored in three bytes, instead of three shorts. Take into
acoount that MD3 as well as MDC stores animation data as vertex coordinates per
frame, this can save quite some memory. Though, in order for compression to work
well, the relative coordinates must fit into a byte. If the animated models
vertexes generally do move across great distances per frame, then compression
is less effective.

The vertex normals are also compressed. The uncompressed normals are stored in
a short value. This value consists of a latitude and a longitude value.
Together they represent the vertex normal in spherical coordinates. The
compressed vertex normals work a bit different. They are precalculated a
certain way. No longitude or latitude values are stored. Instead a byte is used
to point to an array of 256 precalculated normals. The 256 normals are evenly
(more or less) distributed across 3D space, but still fairly precise,
considering it is only 256 values stored by a byte.

For more detailed information on the compressed normals and generally the
MDC format see the document by Wolfgang Prinz called "The MDC File Format".
Also see code comments, especially mdc_file.py is heavily commented.
