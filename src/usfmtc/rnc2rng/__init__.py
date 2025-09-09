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
    import sys, argparse

    argparser = argparse.ArgumentParser()
    argparser.add_argument("infile",help="Input rnc file to convert, - for stdin")
    argparser.add_argument("outfile",nargs="?",help="Output rng file to generate")
    args = argparser.parse_args()

    input = open(args.infile) if args.infile != "-" else sys.stdin
    try:
        xml = serializer.XMLSerializer().toxml(parser.parse(f=input))
    except parser.ParseError as e:
        print('parse error ' + e.msg)
        sys.exit(1)

    if args.outfile:
        open(args.outfile, 'w').write(xml + '\n')
    else:
        print(xml)

if __name__ == '__main__':
    main()

