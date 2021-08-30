#!/usr/bin/python3

import argparse
import re

parser = argparse.ArgumentParser(
    add_help=True,
    description='Read (specially formatted) PlantUML files as database schemas.' )

parser.add_argument("file")

# Parse the command line.
args = parser.parse_args()

current = None
tables = []

class Table:
    def __init__(self, name):
        self.name = name
        self.fields = []
        self.constraints = []
        self.primaries = []

def lookingForTable(line):
    global current
    global state
    assert(current == None)
    if line[:6] == "table(":
        line = line[6:]
        line = line[:line.find(')')]
        #print('Found table', line)
        current = Table(line)
        state = parse_column

class column:
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.primary = False
        self.notNull = False
        self.generated = None
        self.unique = False

class unique:
    def __init__(self, table, line):
        self.name = 'unique'
        self.fields = map(lambda p : p.strip(), line.split(','))
        table.constraints.append(self)
        #print('    unique: {}'.format(','.join(self.fields)))

def parse_TableConstraint(line):
    global current
    global state
    assert(current != None)
    assert(line != '')
    if line.startswith('unique('):
        pass
    else:
        # end of table
        assert(line == '}')
        tables.append(current)
        current = None
        state = lookingForTable

def parse_column(line):
    global current
    global state
    assert(current != None)
    assert(line != '')
    # get the name & type
    m = re.match('(\w+)(\s+|\s*:\s*)(\w+)\s*', line)
    if m:
        name = m[1]
        type = m[3]
        line = line[m.end(0):]

        f = column(name, type)

        while line != '':
            m  = re.match('(primary|notnull|generated)\s*', line)
            if m[1] == 'primary':
                f.primary = True
                line = line[m.end(0):]
            elif m[1] == 'notnull':
                f.notNull = True
                line = line[m.end(0):]
            elif m[1] == 'generated':
                f.generated = line[m.end(0):]
                line = ''
            else:
                raise Exception("Unknown token {}".format(line))
        current.fields.append(f)
    else:
        # we must have hit the end of the columns
        # look for table constraints now
        state = parse_TableConstraint
        return parse_TableConstraint(line)

state = lookingForTable

def cleanup(s):
    p = s.find("'")
    if p >= 0:
        s = s[:p]
    return s.strip()

with open(args.file) as f:
    for l in f:
        l = cleanup(l)
        if l != '---' and l != '':
            state(l)

class SqlFormatter:
    def __init__(self):
        pass

    def column(self, table, f):
        primary = ' PRIMARY KEY' if f.primary else ''
        notnull = ' NOT NULL' if f.notNull else ''
        generated = ' AS {}'.format(f.generated) if f.generated else ''
        return '	{} {}{}{}{}'.format(f.name, f.type.upper(), primary, notnull, generated)

    def generated(self, table, f):
        return '	{} {} AS {}'.format(f.name, f.type.upper(), f.expression)

    def constraint(self, table, name, fields):
        return '	{}({})'.format(name.upper(), ', '.join(fields))

    def table(self, t):
        fields = []
        for f in t.fields:
            handler = getattr(self, f.__class__.__name__)
            fields.append(handler(t, f))
        for c in t.constraints:
            fields.append(self.constraint(t, c.name, c.fields))
        if len(t.primaries) > 1:
            fields.append(self.constraint(t, 'PRIMARY KEY', t.primaries))

        s = 'CREATE TABLE {}(\n'.format(t.name)
        s += ',\n'.join(fields)
        s += '\n);'
        print(s)

formatter = SqlFormatter()

for t in tables:
    formatter.table(t)