#:coding=utf8:

try:
    import json
except ImportError:
    import simplejson as json

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import hashlib
import zipfile
import decimal
from M2Crypto import SMIME
from M2Crypto import X509
from M2Crypto.X509 import X509_Stack


class Alignment:
    LEFT = 'PKTextAlignmentLeft'
    CENTER = 'PKTextAlignmentCenter'
    RIGHT = 'PKTextAlignmentRight'
    JUSTIFIED = 'PKTextAlignmentJustified'
    NATURAL = 'PKTextAlignmentNatural'


class BarcodeFormat:
    PDF417 = 'PKBarcodeFormatPDF417'
    QR = 'PKBarcodeFormatQR'
    AZTEC = 'PKBarcodeFormatAztec'


class TransitType:
    AIR = 'PKTransitTypeAir'
    TRAIN = 'PKTransitTypeTrain'
    BUS = 'PKTransitTypeBus'
    BOAT = 'PKTransitTypeBoat'
    GENERIC = 'PKTransitTypeGeneric'


class DateStyle:
    NONE = 'PKDateStyleNone'
    SHORT = 'PKDateStyleShort'
    MEDIUM = 'PKDateStyleMedium'
    LONG = 'PKDateStyleLong'
    FULL = 'PKDateStyleFull'


class NumberStyle:
    DECIMAL = 'PKNumberStyleDecimal'
    PERCENT = 'PKNumberStylePercent'
    SCIENTIFIC = 'PKNumberStyleScientific'
    SPELLOUT = 'PKNumberStyleSpellOut'


class Field(object):

    def __init__(self, key, value, label='', changeMessage='', textAlignment=Alignment.LEFT):

        self.key = key  # Required. The key must be unique within the scope
        self.value = value  # Required. Value of the field. For example, 42
        self.label = label  # Optional. Label text for the field.
        self.changeMessage = changeMessage  # Optional. Format string for the alert text that is displayed when the pass is updated
        self.textAlignment = textAlignment

    def json_dict(self):
        return self.__dict__


class DateField(Field):

    def __init__(self, key, value, label='', dateStyle=DateStyle.SHORT, timeStyle=DateStyle.SHORT, isRelative=False, *args, **kwargs):
        super(DateField, self).__init__(key, value, label, *args, **kwargs)
        self.dateStyle = dateStyle  # Style of date to display
        self.timeStyle = timeStyle  # Style of time to display
        self.isRelative = isRelative  # If true, the labels value is displayed as a relative date

    def json_dict(self):
        return self.__dict__


class NumberField(Field):

    def __init__(self, key, value, label='', numberStyle=NumberStyle.DECIMAL, *args, **kwargs):
        super(NumberField, self).__init__(key, value, label, *args, **kwargs)
        self.numberStyle = numberStyle  # Style of date to display

    def json_dict(self):
        return self.__dict__


class CurrencyField(NumberField):

    def __init__(self, key, value, label='', currencyCode='', *args, **kwargs):
        super(CurrencyField, self).__init__(key, value, label, *args, **kwargs)
        self.currencyCode = currencyCode  # ISO 4217 currency code

    def json_dict(self):
        return self.__dict__


class Barcode(object):

    def __init__(self, message, format=BarcodeFormat.PDF417, messageEncoding='iso-8859-1', altText=''):

        self.format = format
        self.message = message  # Required. Message or payload to be displayed as a barcode
        self.messageEncoding = messageEncoding  # Required. Text encoding that is used to convert the message
        self.altText = altText  # Optional. Text displayed near the barcode

    def json_dict(self):
        return self.__dict__


class Location(object):

    def __init__(self, latitude, longitude, altitude=0, relevantText=''):

        self.latitude = latitude  # Required. Latitude, in degrees, of the location.
        self.longitude = longitude  # Required. Longitude, in degrees, of the location.
        self.altitude = altitude  # Optional. Altitude, in meters, of the location.
        self.relevantText = relevantText  # Optional. Text displayed on the lock screen when the pass is currently

    def json_dict(self):
        return self.__dict__


class PassInformation(object):

    def __init__(self):
        self.headerFields = []
        self.primaryFields = []
        self.secondaryFields = []
        self.backFields = []
        self.auxiliaryFields = []

    def addHeaderField(self, key, value, label):
        self.headerFields.append(Field(key, value, label))

    def addPrimaryField(self, key, value, label):
        self.primaryFields.append(Field(key, value, label))

    def addSecondaryField(self, key, value, label):
        self.secondaryFields.append(Field(key, value, label))

    def addBackField(self, key, value, label):
        self.backFields.append(Field(key, value, label))

    def addAuxiliaryField(self, key, value, label):
        self.auxiliaryFields.append(Field(key, value, label))

    def json_dict(self):
        d = {}
        if self.headerFields:
            d.update({'headerFields': [f.json_dict() for f in self.headerFields]})
        if self.primaryFields:
            d.update({'primaryFields': [f.json_dict() for f in self.primaryFields]})
        if self.secondaryFields:
            d.update({'secondaryFields': [f.json_dict() for f in self.secondaryFields]})
        if self.backFields:
            d.update({'backFields': [f.json_dict() for f in self.backFields]})
        if self.auxiliaryFields:
            d.update({'auxiliaryFields': [f.json_dict() for f in self.auxiliaryFields]})
        return d


class BoardingPass(PassInformation):

    def __init__(self, transitType=TransitType.AIR):
        super(BoardingPass, self).__init__()
        self.transitType = transitType
        self.jsonname = 'boardingPass'

    def json_dict(self):
        d = super(BoardingPass, self).json_dict()
        d.update({'transitType': self.transitType})
        return d


class Coupon(PassInformation):

    def __init__(self):
        super(Coupon, self).__init__()
        self.jsonname = 'coupon'


class EventTicket(PassInformation):

    def __init__(self):
        super(EventTicket, self).__init__()
        self.jsonname = 'eventTicket'


class Generic(PassInformation):

    def __init__(self):
        super(Generic, self).__init__()
        self.jsonname = 'generic'


class StoreCard(PassInformation):

    def __init__(self):
        super(StoreCard, self).__init__()
        self.jsonname = 'storeCard'


class Pass(object):

    def __init__(self, passInformation, json='', passTypeIdentifier='', organizationName='', teamIdentifier='', serialNumber='', description='', formatVersion=1):

        self._files = {}  # Holds the files to include in the .pkpass
        self._hashes = {}  # Holds the SHAs of the files array

         # Standard Keys
        self.teamIdentifier = teamIdentifier  # Required. Team identifier of the organization that originated and signed the pass, as issued by Apple.
        self.passTypeIdentifier = passTypeIdentifier  # Required. Pass type identifier, as issued by Apple. The value must correspond with your signing certificate. Used for grouping.
        self.organizationName = organizationName  # Required. Display name of the organization that originated and signed the pass.
        self.serialNumber = serialNumber  # Required. Serial number that uniquely identifies the pass.
        self.description = description  # Required. Brief description of the pass, used by the iOS accessibility technologies.
        self.formatVersion = formatVersion  # Required. Version of the file format. The value must be 1.

        # Visual Appearance Keys
        self.backgroundColor = None  # Optional. Background color of the pass
        self.foregroundColor = None  # Optional. Foreground color of the pass,
        self.labelColor = None  # Optional. Color of the label text
        self.logoText = None  # Optional. Text displayed next to the logo
        self.barcode = None  # Optional. Information specific to barcodes.
        self.suppressStripShine = False  # Optional. If true, the strip image is displayed

        # Web Service Keys
        self.webServiceURL = None  # Optional. If present, authenticationToken must be supplied
        self.authenticationToken = None  # The authentication token to use with the web service

        # Relevance Keys
        self.locations = None  # Optional. Locations where the pass is relevant. For example, the location of your store.
        self.relevantDate = None  # Optional. Date and time when the pass becomes relevant

        self.associatedStoreIdentifiers = None  # Optional. A list of iTunes Store item identifiers for the associated apps.

        self.passInformation = passInformation

    # Adds file to the file array
    def addFile(self, name, fd):
        self._files[name] = fd.read()

    # Creates the actual .pkpass file
    def create(self, certificate=None, certificate_str=None, key=None, key_str=None, wwdr_certificate=None, wwdr_certificate_str=None, password=None, zip_file=None):
        pass_json = self._createPassJson()
        manifest = self._createManifest(pass_json)
        signature = self._createSignature(manifest, certificate, certificate_str, key, key_str, wwdr_certificate, wwdr_certificate_str, password)
        if not zip_file:
            zip_file = StringIO()
        self._createZip(pass_json, manifest, signature, zip_file=zip_file)
        return zip_file

    def _createPassJson(self):
        return json.dumps(self, default=PassHandler)

    # creates the hashes for the files and adds them into a json string.
    def _createManifest(self, pass_json):
        # Creates SHA hashes for all files in package
        self._hashes['pass.json'] = hashlib.sha1(pass_json).hexdigest()
        for filename, filedata in self._files.items():
            self._hashes[filename] = hashlib.sha1(filedata).hexdigest()
        return json.dumps(self._hashes)

    # Creates a signature and saves it
    def _createSignature(self, manifest, certificate=None, certificate_str=None, key=None, key_str=None, wwdr_certificate=None, wwdr_certificate_str=None, password=None):
        def passwordCallback(*args, **kwds):
            return password

        # we need to attach wwdr cert as X509
        if wwdr_certificate:
            wwdrcert = X509.load_cert(wwdr_certificate)
        elif wwdr_certificate_str:
            # handle raw certificate strings
            wwdrcert = X509.load_cert_string(wwdr_certificate_str)
        else:
            raise Exception('No WWDR certificate passed to _createSignature')

        stack = X509_Stack()
        stack.push(wwdrcert)

        smime = SMIME.SMIME()
        smime.set_x509_stack(stack)

        if certificate and key:
            # need to cast to string since load_key doesnt work with unicode paths
            smime.load_key(str(key), certificate, callback=passwordCallback)
        elif certificate_str and key_str:
            # handle raw key and certificate strings
            keybio = SMIME.BIO.MemoryBuffer(key_str.encode('utf8'))
            certbio = SMIME.BIO.MemoryBuffer(certificate_str.encode('utf8'))
            smime.load_key_bio(keybio, certbio, callback=passwordCallback)
        else:
            raise Exception('No valid combination of certificate and key passed to _createSignature')

        pk7 = smime.sign(SMIME.BIO.MemoryBuffer(manifest), flags=SMIME.PKCS7_DETACHED | SMIME.PKCS7_BINARY)

        pem = SMIME.BIO.MemoryBuffer()
        pk7.write(pem)
        # convert pem to der
        der = ''.join(l.strip() for l in pem.read().split('-----')[2].splitlines()).decode('base64')

        return der

    # Creates .pkpass (zip archive)
    def _createZip(self, pass_json, manifest, signature, zip_file=None):
        zf = zipfile.ZipFile(zip_file or 'pass.pkpass', 'w')
        zf.writestr('signature', signature)
        zf.writestr('manifest.json', manifest)
        zf.writestr('pass.json', pass_json)
        for filename, filedata in self._files.items():
            zf.writestr(filename, filedata)
        zf.close()

    def json_dict(self):
        d = {
            'description': self.description,
            'formatVersion': self.formatVersion,
            'organizationName': self.organizationName,
            'passTypeIdentifier': self.passTypeIdentifier,
            'serialNumber': self.serialNumber,
            'teamIdentifier': self.teamIdentifier,
            'suppressStripShine': self.suppressStripShine,
            self.passInformation.jsonname: self.passInformation.json_dict()
        }
        if self.barcode:
            d.update({'barcode': self.barcode.json_dict()})
        if self.relevantDate:
            d.update({'relevantDate': self.relevantDate})
        if self.backgroundColor:
            d.update({'backgroundColor': self.backgroundColor})
        if self.foregroundColor:
            d.update({'foregroundColor': self.foregroundColor})
        if self.labelColor:
            d.update({'labelColor': self.labelColor})
        if self.logoText:
            d.update({'logoText': self.logoText})
        if self.locations:
            d.update({'locations': self.locations})
        if self.associatedStoreIdentifiers:
            d.update({'associatedStoreIdentifiers': self.associatedStoreIdentifiers})
        if self.webServiceURL:
            d.update({'webServiceURL': self.webServiceURL,
                      'authenticationToken': self.authenticationToken})
        return d


def PassHandler(obj):
    if hasattr(obj, 'json_dict'):
        return obj.json_dict()
    else:
        # For Decimal latitude and logitude etc.
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        else:
            return obj
