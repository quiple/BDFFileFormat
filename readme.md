# This is a plugin to load and write Glyph Bitmap Distribution Format file.

### Installation

1. Install the Glyph Note plugin via *Window > Plugin Manager*
2. Restart Glyphs.

If you cannot use the Plugin Manager, follow these steps:

1. Download the complete ZIP file and unpack it, or clone the repository.
2. Double click the file `BDF.glyphsFileFormat`. Confirm the dialogs that appear in Glyphs.
3. Restart Glyphs.

### Usage
The plugin uses 100 font units per pixel. For example, for a 16 px font, set the UPM to 1600, the ascender to 1400 or 1300, the descender to -200 or -300, and the grid to 100.

Then add a glyph called `pixel` and draw a 100 by 100 square at the origin. It should look like this:
![Pixel](pixel.png)

