from . import parser, serializer

def load(f):
    return parser.parse(f=f)

def loads(src):
    return parser.parse(src)

def dump(root, f, indent=None):
    f.write(serializer.XMLSerializer(indent).toxml(root))

def dumps(root, indent=None):
    return serializer.XMLSerializer(indent).toxml(root)

def main():
    import sys

    args = sys.argv[1:]
    input = open(args[0]) if len(args) > 0 else sys.stdin
    try:
        xml = serializer.XMLSerializer().toxml(parser.parse(f=input))
    except parser.ParseError as e:
        print('parse error ' + e.msg)
        sys.exit(1)

    if len(args) > 1:
        open(sys.argv[2], 'w').write(xml + '\n')
    else:
        print(xml)

if __name__ == '__main__':
    main()

