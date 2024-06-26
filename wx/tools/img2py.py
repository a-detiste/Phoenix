#----------------------------------------------------------------------
# Name:        wx.tools.img2py
# Purpose:     Convert an image to Python code.
#
# Author:      Robin Dunn
#
# Copyright:   (c) 2002-2020 by Total Control Software
# Licence:     wxWindows license
# Tags:        phoenix-port, py3-port
#----------------------------------------------------------------------
#
# Changes:
#    - Cliff Wells <LogiplexSoftware@earthlink.net>
#      20021206: Added catalog (-c) option.
#
# 12/21/2003 - Jeff Grimmett (grimmtooth@softhome.net)
#        V2.5 compatibility update
#
# 2/25/2007 - Gianluca Costa (archimede86@katamail.com)
#        -Refactorization of the script-creation code in a specific "img2py()" function
#        -Added regex parsing instead of module importing
#        -Added some "try/finally" statements
#        -Added default values as named constants
#        -Made some parts of code a bit easier to read
#        -Updated the module docstring
#        -Corrected a bug with EmptyIcon
#
# 11/26/2007 - Anthony Tuininga (anthony.tuininga@gmail.com)
#        -Use base64 encoding instead of simple repr
#        -Remove compression which doesn't buy anything in most cases and
#         costs more in many cases
#        -Use wx.lib.embeddedimage.PyEmbeddedImage class which has methods
#         rather than using standalone methods
#


"""
img2py.py  --  Convert an image to PNG format and embed it in a Python
               module with appropriate code so it can be loaded into
               a program at runtime.  The benefit is that since it is
               Python source code it can be delivered as a .pyc or
               'compiled' into the program using freeze, py2exe, etc.

Usage:

    img2py.py [options] image_file python_file

Options:

    -m <#rrggbb>   If the original image has a mask or transparency defined
                   it will be used by default.  You can use this option to
                   override the default or provide a new mask by specifying
                   a colour in the image to mark as transparent.

    -n <name>      Normally generic names (getBitmap, etc.) are used for the
                   image access functions.  If you use this option you can
                   specify a name that should be used to customize the access
                   functions, (getNameBitmap, etc.)

    -c             Maintain a catalog of names that can be used to reference
                   images.  Catalog can be accessed via catalog and
                   index attributes of the module.
                   If the -n <name> option is specified then <name>
                   is used for the catalog key and index value, otherwise
                   the filename without any path or extension is used
                   as the key.

    -a             This flag specifies that the python_file should be appended
                   to instead of overwritten.  This in combination with -n will
                   allow you to put multiple images in one Python source file.

    -i             Also output a function to return the image as a wxIcon.

    -f             Generate code compatible with the old function interface.
                   (This option is ON by default in 2.8, use -f to turn off.)

You can also import this module from your Python scripts, and use its img2py()
function. See its docstring for more info.
"""

import base64
import getopt
import os
import re
import sys
import tempfile

import wx
from wx.tools import img2img

try:
    b64encode = base64.b64encode
except AttributeError:
    b64encode = base64.encodestring

app = None
DEFAULT_APPEND = False
DEFAULT_COMPRESSED = True
DEFAULT_MASKCLR = None
DEFAULT_IMGNAME = ""
DEFAULT_ICON = False
DEFAULT_CATALOG = False
DEFAULT_COMPATIBLE = False

# THIS IS USED TO IDENTIFY, IN THE GENERATED SCRIPT, LINES IN THE FORM
# "index.append('Image name')"
indexPattern = re.compile(r"\s*index.append\('(.+)'\)\s*")


def convert(fileName, maskClr, outputDir, outputName, outType, outExt):
    # if the file is already the right type then just use it directly
    if maskClr == DEFAULT_MASKCLR and fileName.upper().endswith(outExt.upper()):
        if outputName:
            newname = outputName
        else:
            newname = os.path.join(outputDir,
                                   os.path.basename(os.path.splitext(fileName)[0]) + outExt)
        with open(newname, "wb") as f_out:
            with open(fileName, "rb") as f_in:
                f_out.write(f_in.read())
        return True, "ok"
    return img2img.convert(fileName, maskClr, outputDir, outputName, outType, outExt)


def _replace_non_alphanumeric_with_underscore(imgName):
    letters = [letter if letter.isalnum() else '_' for letter in imgName]

    if not letters[0].isalpha() and letters[0] != '_':
        letters.insert(0, "_")
    varName = "".join(letters)
    return varName


def _write_image(out, imgName, data, append, icon, catalog, functionCompatible, old_index):
    out.write("#" + "-" * 70 + "\n")
    if not append:
        out.write("# This file was generated by %s\n#\n" % sys.argv[0])
        out.write("from wx.lib.embeddedimage import PyEmbeddedImage\n\n")
        if catalog:
            out.write("catalog = {}\n")
            out.write("index = []\n\n")
    varName = _replace_non_alphanumeric_with_underscore(imgName)
    out.write("%s = PyEmbeddedImage(\n%s\n" % (varName, data))
    if catalog:
        if imgName in old_index:
            print("Warning: %s already in catalog." % imgName)
            print("         Only the last entry will be accessible.\n")
        old_index.append(imgName)
        out.write("index.append('%s')\n" % imgName)
        out.write("catalog['%s'] = %s\n" % (imgName, varName))
    if functionCompatible:
        out.write("get%sData = %s.GetData\n" % (varName, varName))
        out.write("get%sImage = %s.GetImage\n" % (varName, varName))
        out.write("get%sBitmap = %s.GetBitmap\n" % (varName, varName))
        if icon:
            out.write("get%sIcon = %s.GetIcon\n" % (varName, varName))
    out.write("\n")


def img2py(image_file, python_file,
           append=DEFAULT_APPEND,
           compressed=DEFAULT_COMPRESSED,
           maskClr=DEFAULT_MASKCLR,
           imgName=DEFAULT_IMGNAME,
           icon=DEFAULT_ICON,
           catalog=DEFAULT_CATALOG,
           functionCompatible=DEFAULT_COMPATIBLE,
           functionCompatibile=-1,   # typo version for backward compatibility
           ):
    """
    Converts an image file to a data structure written in a Python file
    --image_file: string; the path of the source image file
    --python_file: string; the path of the destination python file
    --other arguments: they are equivalent to the command-line arguments
    """

    # was the typo version used?
    if functionCompatibile != -1:
        functionCompatible = functionCompatibile

    global app
    if not wx.GetApp():
        app = wx.App(0)

    # convert the image file to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as fid:
        tfname = fid.name

    try:
        ok, msg = convert(image_file, maskClr, None, tfname, wx.BITMAP_TYPE_PNG, ".png")
        if not ok:
            print(msg)
            return

        lines = []
        with open(tfname, "rb") as fid:
            data = b64encode(fid.read())
        while data:
            part = data[:72]
            data = data[72:]
            output = '    %s' % part
            if not data:
                output += ")"
            lines.append(output)
        data = "\n".join(lines)
    finally:
        if os.path.exists(tfname):
            os.remove(tfname)

    old_index = []
    if catalog and append and python_file != '-':
        # check to see if catalog exists already (file may have been created
        # with an earlier version of img2py or without -c option)
        pyPath, pyFile = os.path.split(python_file)

        append_catalog = True

        with open(python_file, "r") as sourcePy:
            for line in sourcePy:
                if line == "catalog = {}\n":
                    append_catalog = False
                else:
                    lineMatcher = indexPattern.match(line)
                    if lineMatcher:
                        old_index.append(lineMatcher.groups()[0])

        if append_catalog:
            with open(python_file, "a") as out:
                out.write("\n# ***************** Catalog starts here *******************")
                out.write("\n\ncatalog = {}\n")
                out.write("index = []\n\n")

    if not imgName:
        imgPath, imgFile = os.path.split(image_file)
        imgName = os.path.splitext(imgFile)[0]
        print("\nWarning: -n not specified. Using filename (%s) for name of image and/or catalog entry." % imgName)

    if python_file == '-':
        out = sys.stdout
        _write_image(out, imgName, data, append, icon, catalog, functionCompatible, old_index)
    else:
        mode = "a" if append else "w"
        with open(python_file, mode) as out:
            _write_image(out, imgName, data, append, icon, catalog, functionCompatible, old_index)

    if imgName:
        n_msg = ' using "%s"' % imgName
    else:
        n_msg = ""

    if maskClr:
        m_msg = " with mask %s" % maskClr
    else:
        m_msg = ""

    print("Embedded %s%s into %s%s" % (image_file, n_msg, python_file, m_msg))

def main(args=None):
    if not args:
        args = sys.argv[1:]

    if not args or ("-h" in args):
        print(__doc__)
        return

    append = DEFAULT_APPEND
    compressed = DEFAULT_COMPRESSED
    maskClr = DEFAULT_MASKCLR
    imgName = DEFAULT_IMGNAME
    icon = DEFAULT_ICON
    catalog = DEFAULT_CATALOG
    compatible = DEFAULT_COMPATIBLE

    try:
        opts, fileArgs = getopt.getopt(args, "auicfFn:m:")
    except getopt.GetoptError:
        print(__doc__)
        return

    for opt, val in opts:
        if opt == "-a":
            append = True
        elif opt == "-n":
            imgName = val
        elif opt == "-m":
            maskClr = val
        elif opt == "-i":
            icon = True
        elif opt == "-c":
            catalog = True
        elif opt == "-f":
            compatible = True
        elif opt == "-F":
            compatible = False

    if len(fileArgs) != 2:
        print(__doc__)
        return

    image_file, python_file = fileArgs
    img2py(image_file, python_file,
           append, compressed, maskClr, imgName, icon, catalog, compatible)


if __name__ == "__main__":
    main(sys.argv[1:])
