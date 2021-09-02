#!/usr/bin/python3

import argparse
import re

parser = argparse.ArgumentParser(
    add_help=True,
    description='Read (specially formatted) PlantUML files as database schemas.' )

parser.add_argument("file")

# Parse the command line.
args = parser.parse_args()

tables = []
views = []

class column:
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.primary = False
        self.notNull = False
        self.generated = None
        self.unique = False

class unique:
    def __init__(self, line):
        assert(line.startswith('unique('))
        assert(line[-1] == ')')
        line = line[7:-1]
        self.name = 'unique'
        self.fields = map(lambda p : p.strip(), line.split(','))

class Table:
    def __init__(self, name):
        self.name = name
        self.fields = []
        self.constraints = []
        self.primaries = []

    def parse_TableConstraint(self, line):
        assert(line != '')
        if line.startswith('unique('):
            c = unique(line)
            self.constraints.append(c)
            return self.parse_TableConstraint
        else:
            # end of table
            assert(line == '}')
            return lookingForTable

    def parse_column(self, line):
        assert(line != '')
        # get the name & type
        m = re.match('(\w+)(\s+|\s*:\s*)(\w+)\s*', line)
        if m:
            name = m[1]
            type = m[3]
            line = line[m.end(0):]

            f = column(name, type)

            while line != '':
                m  = re.match('(primary|notnull|unique|generated)\s*', line)
                if m[1] == 'primary':
                    f.primary = True
                    line = line[m.end(0):]
                    self.primaries.append(name)
                elif m[1] == 'notnull':
                    f.notNull = True
                    line = line[m.end(0):]
                elif m[1] == 'unique':
                    f.unique = True
                elif m[1] == 'generated':
                    f.generated = line[m.end(0):]
                    line = ''
                else:
                    raise Exception("Unknown token {}".format(line))
            self.fields.append(f)
            return self.parse_column
        else:
            # we must have hit the end of the columns
            # look for table constraints now
            return self.parse_TableConstraint(line)

class View:
    def __init__(self, name):
        self.name = name
        print("Creating view: {}".format(name))

    def parse_join(self, line):
        assert(line != '')
        # get the name & type
        m = re.match('(\w+)\.(\w+)\s*(<-|->)\s*(\w+)\.(\w+)', line)
        if m:
            self.table1 = (m[1], m[2])
            self.table2 = (m[4], m[5])
            self.join = 'left join' if m[3] == '<-' else 'join'
            line = line[m.end(0):]
            return self.parse_join
        else:
            # end of table
            assert(line == '}')
            return lookingForTable

def lookingForTable(line):
    if line[:6] == "table(":
        line = line[6:line.find(')')]
        #print('Found table', line)
        table = Table(line)
        tables.append(table)
        return table.parse_column
    elif line[:5] == 'view(':
        line = line[5:line.find(')')]
        view = View(line)
        views.append(view)
        return view.parse_join
    else:
        return lookingForTable

state = lookingForTable

def cleanup(s):
    p = s.find("'")
    if p >= 0:
        s = s[:p]
    # skip comments
    s = s.strip()
    if s == '---' or l == '':
        s = None
    return s

with open(args.file) as f:
    for l in f:
        l = cleanup(l)
        if l:
            state = state(l)

class SqlFormatter:
    def __init__(self):
        pass

    def column(self, table, f):
        # If only one field is marked as a primary key
        # then we should add that as a field constraint.
        constraint =  ' PRIMARY KEY' if (len(table.primaries) == 1 and f.primary) else ''
        constraint += ' NOT NULL' if f.notNull else ''
        constraint += ' UNIQUE' if f.unique else ''
        constraint += ' AS {}'.format(f.generated) if f.generated else ''
        return '    {} {}{}'.format(f.name, f.type.upper(), constraint)

    def constraint(self, table, name, fields):
        return '    {}({})'.format(name.upper(), ', '.join(fields))

    def formatTable(self, table):
        fields = ['CREATE TABLE {}('.format(table.name)]

        for f in table.fields:
            handler = getattr(self, f.__class__.__name__)
            fields.append(handler(table, f))
        for c in table.constraints:
            fields.append(self.constraint(table, c.name, c.fields))
        # If more than one field is marked as a primary key then we need
        # to add a table constraint to specify them.
        if len(table.primaries) > 1:
            fields.append(self.constraint(table, 'PRIMARY KEY', table.primaries))

        fields[-1] += ');'
        return fields

    def formatView(self, view):
        fields = ['CREATE VIEW {} as'.format(view.name)]

        fields.append("    select * from {t1} {join} {t2} on {t1}.{c1} == {t2}.{c2};"
            .format(t1=view.table1[0], c1=view.table1[1],
                    t2=view.table2[0], c2=view.table2[1],
                    join=view.join))
        return fields

class CppFormatter:
    def __init__(self):
        self._sql = SqlFormatter()

    def formatTable(self, table):
        lines = ['const char* create_{} = R"sql('.format(table.name)]
        prefix = ' ' * 4
        for l in self._sql.formatTable(table):
            lines.append('{}{}'.format(prefix, l))

        if lines[-1][-1] == ';':
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1] + ')sql";'
        return lines

    def formatView(self, view):
        lines = ['const char* create_{} = R"sql('.format(view.name)]
        prefix = ' ' * 4
        for l in self._sql.formatView(view):
            lines.append('{}{}'.format(prefix, l))

        if lines[-1][-1] == ';':
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1] + ')sql";'
        return lines

formatter = CppFormatter()

for t in tables:
    lines = formatter.formatTable(t)
    print('\n'.join(lines))
    print('')

for v in views:
    lines = formatter.formatView(v)
    print('\n'.join(lines))
    print('')
