# encoding: utf-8

###########################################################################################################
#
#
#	File Format Plugin
#	Implementation for exporting fonts through the Export dialog
#
#	Read the docs:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/File%20Format
#
#	For help on the use of Interface Builder:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates
#
#
###########################################################################################################

from __future__ import print_function
from GlyphsApp import *
from GlyphsApp.plugins import *
from GlyphsApp.plugins import pathForResource
import os, traceback, math, objc
from CoreFoundation import CFSTR, CFStringCompare
from LaunchServices import LSCopyDefaultRoleHandlerForContentType, LSSetDefaultRoleHandlerForContentType, kLSRolesEditor

UNITS_PER_PIXEL = 100
TRANSFORM_TOLERANCE = 0.01


def pixelOrigin(transform, factor, glyphName):
	"""Return the grid cell covered by a transformed pixel component."""
	a, b, c, d, tx, ty = transform
	if a == 1 and b == 0 and c == 0 and d == 1:
		gridX = tx / factor
		gridY = ty / factor
	else:
		width = factor * (abs(a) + abs(c))
		height = factor * (abs(b) + abs(d))
		if abs(width - factor) > TRANSFORM_TOLERANCE or abs(height - factor) > TRANSFORM_TOLERANCE:
			raise ValueError("%s contains a scaled or skewed pixel component" % glyphName)
		gridX = tx / factor + min(0, a) + min(0, c)
		gridY = ty / factor + min(0, b) + min(0, d)
	roundedX = round(gridX)
	roundedY = round(gridY)
	if abs(gridX - roundedX) > TRANSFORM_TOLERANCE or abs(gridY - roundedY) > TRANSFORM_TOLERANCE:
		raise ValueError("%s contains a pixel component outside the pixel grid" % glyphName)
	return int(roundedX), int(roundedY)


def pixelBounds(pixels):
	"""Return BDF bounds for a non-empty collection of pixel coordinates."""
	iterator = iter(pixels)
	firstX, firstY = next(iterator)
	minX = maxX = firstX
	minY = maxY = firstY
	for x, y in iterator:
		if x < minX:
			minX = x
		elif x > maxX:
			maxX = x
		if y < minY:
			minY = y
		elif y > maxY:
			maxY = y
	return minX, minY, maxX - minX + 1, maxY - minY + 1

class BDFFileFormat(FileFormatPlugin):

	# Definitions of IBOutlets

	# The NSView object from the User Interface. Keep this here!
	dialog = objc.IBOutlet()

	# Example variables. You may delete them
	feedbackTextField = objc.IBOutlet()
	unicodeCheckBox = objc.IBOutlet()
	glyphWidthCheckbox = objc.IBOutlet()

	@objc.python_method
	def settings(self):
		self.name = "BDF"
		self.icon = 'ExportIcon'
		self.toolbarPosition = 200

		# Load .nib dialog (with .extension)
		self.loadNib('IBdialog', __file__)

	@objc.python_method
	def start(self):
		Command = "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister";
		appPath = pathForResource("BDFApp", "app", __file__)
		Command += " \""+appPath+"\""
		os.system(Command)

		handler = LSCopyDefaultRoleHandlerForContentType(CFSTR("org.x.bdf"), kLSRolesEditor)
		identifier = NSBundle.mainBundle().bundleIdentifier()
		if not handler or CFStringCompare(handler, CFSTR(identifier), 0):
			LSSetDefaultRoleHandlerForContentType(CFSTR("org.x.bdf"), kLSRolesEditor, CFSTR(identifier))

	@objc.python_method
	def export(self, font, filepath = None):

		if filepath is None:
			# Ask for export destination and write the file:
			title = "Choose export destination"
			proposedFilename = font.familyName
			fileTypes = ['bdf']
			# Call dialog
			filepath = GetSaveFile(title, proposedFilename, fileTypes)

		self.preExport(font)

		with open(filepath, "w") as f:
			self.writeFontInfo(font, f)
			self.writeGlyphs(font, f)
			f.write("ENDFONT")
		return True, None

	@objc.python_method
	def preExport(self, font):
		self.factor = UNITS_PER_PIXEL
		self.pixel = "pixel"
		if "BDFpixel" in font.customParameters:
			self.pixel = font.customParameters["BDFpixel"]
		self.size = round(font.upm / self.factor)
		master = font.masters[0]
		self.ascender = round(master.ascender / self.factor)
		self.descender = round(master.descender / self.factor)
		self.masterId = master.id
		self.pixelGlyph = font.glyphs[self.pixel]
		if self.pixelGlyph is None:
			raise ValueError("Missing pixel glyph: %s" % self.pixel)
		self.pixelCache = {}
		self.pixelStack = set()
		self.glyphData = {}

		minX = 0
		minY = self.descender
		maxX = self.size
		maxY = self.size + self.descender
		gcount = 0
		for g in font.glyphs:
			if not g.export:
				continue
			layer = g.layers[self.masterId]
			pixels = self.pixelsForLayer(layer)
			if pixels:
				bounds = pixelBounds(pixels)
				originX, originY, width, height = bounds
				minX = min(minX, originX)
				minY = min(minY, originY)
				maxX = max(maxX, originX + width)
				maxY = max(maxY, originY + height)
			else:
				bounds = (0, 0, 0, 0)
			self.glyphData[g.name] = (pixels, bounds)
			gcount += 1

		self.originX = minX
		self.originY = minY
		self.width = maxX - minX
		self.height = maxY - minY
		self.count = gcount

	@objc.python_method
	def writeFontInfo(self, font, f):

		self.resolution = 75
		if "BDFresultion" in font.customParameters:
			self.resolution = int(font.customParameters["BDFresultion"])
		f.write("STARTFONT 2.1\n")
		f.write("FONT %s\n" % font.familyName)
		f.write("SIZE %d %d %d\n" % (self.size, self.resolution, self.resolution))
		f.write("FONTBOUNDINGBOX %d %d %d %d\n" % (self.width, self.height, self.originX, self.originY))
		f.write("STARTPROPERTIES 2\n")
		f.write("FONT_ASCENT %d\n" % self.ascender)
		f.write("FONT_DESCENT %d\n" % abs(self.descender))
		f.write("ENDPROPERTIES\n")

	@objc.python_method
	def pixelsForLayer(self, layer):
		glyphName = layer.parent.name
		key = (glyphName, layer.layerId)
		if key in self.pixelCache:
			return self.pixelCache[key]
		if key in self.pixelStack:
			raise ValueError("Component cycle found at %s" % glyphName)

		self.pixelStack.add(key)
		pixels = set()
		try:
			for component in layer.components:
				componentTransform = component.transform
				if component.componentFast() is self.pixelGlyph:
					pixels.add(pixelOrigin(componentTransform, self.factor, glyphName))
					continue

				componentLayer = component.componentLayer
				if componentLayer is None:
					raise ValueError(
						"%s contains a missing component: %s" % (glyphName, component.componentName)
					)
				childPixels = self.pixelsForLayer(componentLayer)
				a, b, c, d, tx, ty = componentTransform
				if abs(a - 1) <= TRANSFORM_TOLERANCE and abs(b) <= TRANSFORM_TOLERANCE and abs(c) <= TRANSFORM_TOLERANCE and abs(d - 1) <= TRANSFORM_TOLERANCE:
					offsetX, offsetY = pixelOrigin(componentTransform, self.factor, glyphName)
					if offsetX == 0 and offsetY == 0:
						pixels.update(childPixels)
					else:
						pixels.update((x + offsetX, y + offsetY) for x, y in childPixels)
				else:
					for x, y in childPixels:
						transformedPixel = (
							a, b, c, d,
							a * x * self.factor + c * y * self.factor + tx,
							b * x * self.factor + d * y * self.factor + ty,
						)
						pixels.add(pixelOrigin(transformedPixel, self.factor, glyphName))
		finally:
			self.pixelStack.remove(key)

		self.pixelCache[key] = frozenset(pixels)
		return self.pixelCache[key]

	@objc.python_method
	def writeBitmap(self, pixelsForGlyph, originX, originY, width, height, f):
		columns = ((width + 7) // 8) * 8
		rows = [0] * height
		for x, y in pixelsForGlyph:
			row = height - (y - originY) - 1
			column = x - originX
			rows[row] |= 1 << (columns - column - 1)
		f.write("BITMAP\n")
		rowFormat = "%0" + str(columns // 4) + "X\n"
		for row in rows:
			f.write(rowFormat % row)

	@objc.python_method
	def writeGlyph(self, glyph, f):
		layer = glyph.layers[self.masterId]
		pixels, bounds = self.glyphData[glyph.name]

		f.write("STARTCHAR %s\n" % glyph.name)
		if glyph.unicode and len(glyph.unicode) >=4:
			enc = int(glyph.unicode, 16)
			f.write("ENCODING %d\n" % enc)
		f.write("SWIDTH %d 0\n" % ((75 / self.resolution) * 1000.0 * layer.width / (self.factor * self.size)))
		f.write("DWIDTH %d 0\n" % round(layer.width / self.factor))

		originX, originY, width, height = bounds
		f.write("BBX %d %d %d %d\n" % (width, height, originX, originY))
		self.writeBitmap(pixels, originX, originY, width, height, f)
		f.write("ENDCHAR\n")

	@objc.python_method
	def writeGlyphs(self, font, file):
		file.write("CHARS %d\n" % self.count)
		for g in font.glyphs:
			if not g.export:
				continue
			self.writeGlyph(g, file)

	@objc.python_method
	def readFontInfo(self, font, file):
		for line in file:
			if line.startswith("ENDPROPERTIES"):
				return
			if line.startswith("FONT "):
				font.familyName = line[5:-1]
			elif line.startswith("SIZE "):
				size = line.split(" ")
				self.size = int(size[1])
				font.upm = self.size * UNITS_PER_PIXEL
				font.grid = UNITS_PER_PIXEL

				resultion = int(size[2])
				if resultion != 75:
					font.customParameters["BDFresultion"] = resultion

			elif line.startswith("FONT_ASCENT "):
				self.ascender = int(line.split(" ")[1])
				master = font.masters[0]
				master.ascender = self.ascender * UNITS_PER_PIXEL
				master.capHeight = (self.ascender - 1) * UNITS_PER_PIXEL
				master.xHeight = round(self.ascender * 0.66) * UNITS_PER_PIXEL
			elif line.startswith("FONT_DESCENT "):
				self.descender = int(line.split(" ")[1])
				master = font.masters[0]
				master.descender = - self.descender * UNITS_PER_PIXEL
			elif line.startswith("FAMILY_NAME "):
				if font.familyName != "new Font":
					font.customParameters["postscriptFontName"] = font.familyName
				font.familyName = line[12:-1].strip("\" ")
			elif line.startswith("FOUNDRY "):
				font.manufacturer = line[8:-1].strip("\" ")
			elif line.startswith("WEIGHT_NAME "):
				if len(font.instances) == 0:
					instance = GSInstance()
					font.instances.append(instance)
				else:
					instance = font.instances[0]
				instance.name = line[12:-1].strip("\" ")
			elif line.startswith("COPYRIGHT "):
				font.copyright = line[10:-1].strip("\" ")
			elif line.startswith("FONT_VERSION "):
				versionString = line[13:-1].strip("\" ")
				try:
					version = versionString.split(".")
					font.versionMajor = int(version[0])
					font.versionMinor = int(version[1])
				except:
					pass
			elif line.startswith("UNDERLINE_POSITION "):
				master = font.masters[0]
				master.customParameters["underlinePosition"] = int(line[19:-1]) * UNITS_PER_PIXEL
			elif line.startswith("UNDERLINE_THICKNESS "):
				master = font.masters[0]
				master.customParameters["underlineThickness"] = int(line[20:-1]) * UNITS_PER_PIXEL

	@objc.python_method
	def drawPixel(self, font):
		pixel = GSGlyph()
		pixel.name = "pixel"
		pixel.export = False
		font.glyphs.append(pixel)
		layer = pixel.layers[0]
		layer.width = UNITS_PER_PIXEL
		path = GSPath()

		Node = GSNode(NSPoint(UNITS_PER_PIXEL, 0), LINE)
		path.nodes.append(Node)
		Node = GSNode(NSPoint(UNITS_PER_PIXEL, UNITS_PER_PIXEL), LINE)
		path.nodes.append(Node)
		Node = GSNode(NSPoint(0, UNITS_PER_PIXEL), LINE)
		path.nodes.append(Node)
		Node = GSNode(NSPoint(0, 0), LINE)
		path.nodes.append(Node)

		path.closed = True
		layer.paths.append(path)

	@objc.python_method
	def readBitmap(self, layer, originX, originY, width, height, file):
		if width <= 0 or height <= 0:
			return

		row = 0
		columns = int(math.ceil(width / 8.0))
		highesBit = 1 << (columns * 8 - 1)
		layer.setDisableUpdates()
		for line in file:
			line = line.strip()
			if not line:
				continue
			bit = int(line, 16)
			for column in range(width):
				if (bit & highesBit) == highesBit:
					pixel = GSComponent("pixel")
					pixel.position = NSPoint((originX + column) * UNITS_PER_PIXEL, (height - row + originY - 1) * UNITS_PER_PIXEL)
					pixel.automaticAlignment = False
					layer.components.append(pixel)
				bit = bit << 1
			row += 1
			if row >= height:
				break
		layer.enableFutureUpdates()

	@objc.python_method
	def readGlyph(self, glyph, master, file):
		layer = GSLayer()
		glyph.layers[master.id] = layer
		originX = 0
		originY = self.descender
		width = self.size
		height = self.size
		for line in file:
			if line.startswith("ENDCHAR"):
				break
			elif line.startswith("ENCODING"):
				enc = int(line[9:-1])
				uni = "%04X" % enc
				glyph.unicode = uni
			elif line.startswith("DWIDTH"):
				width = int(line.split(" ")[1])
				layer.width = width * UNITS_PER_PIXEL
			elif line.startswith("BBX"):
				elements = line.split(" ")
				originX = int(elements[3])
				originY = int(elements[4])
				width = int(elements[1])
				height = int(elements[2])
			elif line.startswith("BITMAP"):
				self.readBitmap(layer, originX, originY, width, height, file)
				break

	@objc.python_method
	def readGlyphs(self, font, file):
		glyphs = []
		master = font.masters[0]
		niceNames = not Glyphs.boolDefaults["ImportKeepGlyphsNames"]
		for line in file:
			if line.startswith("ENDFONT"):
				break
			if line.startswith("STARTCHAR "):
				glyph = GSGlyph()
				glyph.undoManager().disableUndoRegistration()
				name = line[10:-1]
				if niceNames:
					if name.startswith("U+"):
						name = "uni"+name[2:]
					newName = Glyphs.niceGlyphName(name)
					if newName is not None:
						name = newName
				glyph.name = name

				glyphs.append(glyph)
				glyph.parent = font
				self.readGlyph(glyph, master, file)
				glyph.undoManager().enableUndoRegistration()
		font.glyphs.extend(glyphs)
		self.drawPixel(font)

	@objc.python_method
	def read(self, filepath, fileType):
		font = GSFont()
		font.disableUpdateInterface()
		with open(filepath) as f:
			self.readFontInfo(font, f)
			self.readGlyphs(font, f)
		font.enableUpdateInterface()
		return font

	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
