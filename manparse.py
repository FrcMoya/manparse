# Author: Francisco Moya <frcmoyam@gmail.com>


"""Command-line parsing library

This module is a argparse-inspired command-line parsing library that:

   - customized man like help
   - all parameters must be with -x or --xx format
   - handles compression of short parameters. eg: -abcd -e
   
The following is a simple usage example that sums integers from the
command-line and writes the result to a file:

   parser = manparse.ParameterParser(
       description = "sum the integers at the command line")
   parser.add_parameter('-i', '--integers',
       type=int,
       nargs='+',
       section='Required'
       help="list of integers to be summed")
   parser.add_parameter('-l', '--log',
       type=manparse.FileType('w'),
       default=log.txt,
       section='Optional'
       help="the file where the sum should be written")
   result = parser.parse_args()
"""

__all__ = [
    'ParameterParser'
    'Namespace'
    'FileType'
    'DirType'
    'SUPPRESS'
    'ParameterError'
]


import __builtin__ as _ori
import copy as _copy
import os as _os
import re as _re
import sys as _sys

SUPPRESS = '==SUPPRESS=='
   
def _check_type(ptype, value):
    try:
        ptype(value)
        return True
    except (ValueError, IOError):
        return False
        

def _check_choices(choices, value):
    return True if choices is None or value in choices else False

def _parse_list(parameter, slist):
    if _ori.type(parameter.nargs) is int and parameter.nargs > len(slist):
        msg = "needs %s values" % (parameter.nargs)
        raise ParameterError(parameter, msg)
    list_values = []
    for value in slist:
        # Check if value is a valid value and not a parameter
        if _check_type(int, value) or not value.startswith('-'):
            if _check_type(parameter.type, value):
                value = parameter.type(value)
                if _check_choices(parameter.choices, value):
                    list_values.append(value)
                else:
                    msg = "'%s' not in choices %s" % (value, parameter.choices)
                    raise ParameterError(parameter, msg)
            else:
                msg = "'%s' is not %s" % (value, parameter.type)
                raise ParameterError(parameter, msg)
        else:
            msg = "'%s' is not a valid value" % (value)
            raise ParameterError(parameter, msg)
        
    return list_values


class ParameterError(Exception):
    """An error from creating or using an argument
    """
    
    def __init__(self, parameter, message):
        if parameter is None:
            self.parameter_name = None
        else:
            self.parameter_name = parameter.name
        self.message = message
    
    def __str__(self):
        if self.parameter_name is None:
            format = '%(message)s'
        else:
            format = 'parameter %(parameter_name)s: %(message)s'
        return format % dict(message=self.message,
                             parameter_name=self.parameter_name)


class FileType(object):
    """Factory for creating file object types

    Instances of FileType are typically passed as type= arguments to the
    ParameterParser add_parameter() method.

    Keyword Arguments:
        - mode -- A string indicating how the file is to be opened. Accepts the
            same values as the builtin open() function.
        - bufsize -- The file's desired buffer size. Accepts the same values as
            the builtin open() function.
    """

    def __init__(self, mode='r', bufsize=None):
        self._mode = mode
        self._bufsize = bufsize

    def __call__(self, string):
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                return _sys.stdin
            elif 'w' in self._mode:
                return _sys.stdout
            else:
                msg = ('argument "-" with mode %r' % self._mode)
                raise ValueError(msg)
        try:
            if self._mode not in ['r', 'w']:
                msg = "'%s' is not a valid mode for FileType. Valid modes: 'r', 'w'" % (self._mode)
                raise ParameterError(None, msg)
            if self._bufsize:
                return open(string, self._mode, self._bufsize)
            else:
                return open(string, self._mode)
        except IOError:
            err = _sys.exc_info()[1]
            message = "cannot open '%s': %s"
            raise ParameterError(None, message % (string, err))

    def __repr__(self):
        args = [self._mode, self._bufsize]
        args_str = ', '.join([repr(arg) for arg in args if arg is not None])
        return "%s(%s)" % (type(self).__name__, args_str)
    
    def __cmp__(self, other):
        return 0
    
    def __eq__(self, other):
        if other is FileType:
            return True
        else:
            return False


class DirType(object):
    """Factory for creating dir object types

    TODO DOCSTRING
    """

    def __init__(self, check=False):
        self.check = check
    
    def __call__(self, string):
        if type(string) is not str:
            msg = "%s must be 'str' type"
            raise ParameterError(None, msg)
        if self.check:
            if not _os.path.isdir(string):
                msg = "%s is not an actual directory" % (string)
                raise ParameterError(None, msg)
        return string
    
    def __repr__(self):
        return "%s(check=%s)" % (type(self).__name__, self.check)
        
    def __cmp__(self, other):
        return 0
    
    def __eq__(self, other):
        if other is DirType:
            return True
        else:
            return False


class _AttributeHolder(object):
    """Abstract base class that provides __repr__.

    The __repr__ method returns a string in the format::
        ClassName(attr=name, attr=name, ...)
    The attributes are determined either by a class-level attribute,
    '_kwarg_names', or by inspecting the instance __dict__.
    """
    
    def __repr__(self):
        type_name = type(self).__name__
        arg_strings = []
        for arg in self._get_args():
            arg_strings.append(repr(arg))
        for name, value in self._get_kwargs():
            arg_strings.append('%s=%r' % (name, value))
        return '%s(%s)' % (type_name, ', '.join(arg_strings))

    def _get_kwargs(self):
        return sorted(self.__dict__.items())

    def _get_args(self):
        return []
    

class Namespace(_AttributeHolder):
    """Simple object for storing attributes.

    Implements equality by attribute names and values, and provides a simple
    string representation.
    """

    def __init__(self, **kwargs):
        for name in kwargs:
            setattr(self, name, kwargs[name])

    __hash__ = None

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __ne__(self, other):
        return not (self == other)

    def __contains__(self, key):
        return key in self.__dict__
    
    def __iter__(self):
        return iter([a for a in dir(self) if not a.startswith('_') and a is not 'next'])


class _Parameter(object):
    """Object that represent a parameter
    """
    
    def __init__(self, name, long_name, dest,
                 type=None,
                 action='store',
                 nargs=None,
                 default=None,
                 const=None,
                 required=False,
                 choices=None,
                 section=None,
                 help=None):
        
        self.name = name
        self.long_name = long_name
        self.dest = dest
        
        # Transform to bool
        self.required = bool(required)
        
        # Section in help
        if self.required is True:
            section = "Required"
        if section is None:
            section = "Others"
        self.section = section
    
        
        # Type check
        if type is None:
            type = str
        if type in [str, int, float, bool, FileType, DirType]:
            self.type = type
        else:
            msg = "not valid type '%s'. Valid types: str, int, float, bool, 'FileType', 'DirType'" % (type)
            raise ParameterError(self, msg)
            
        # Action check
        if action in ['store', 'store_true', 'store_false', 'help', 'version']:
            self.action = action
            if self.action == 'store_true':
                default = False
            if self.action == 'store_false':
                default = True
        else:
            msg = "not valid action '%s'. Valid actions: 'store', 'store_true', 'store_false', 'help', 'version'" % (action)
            raise ParameterError(self, msg)
        
        # Default type conversion if it is necessary
        if default not in [None, SUPPRESS]:
            if not _check_type(self.type, default):
                msg = "default value '%s' is not '%s'" % (default, self.type)
                raise ParameterError(self, msg)
            default = self.type(default)
        self.default = default
        
        # Const type conversion if it is necessary
        if const is not None:
            if not _check_type(self.type, const):
                msg = "const value '%s' is not '%s'" % (const, self.type)
                raise ParameterError(self, msg)
            const = self.type(const)
        self.const = const
        
        # Check choices
        if choices is not None:
            if hasattr(choices, '__iter__'):
                choices = [self.type(i) for i in choices]
            else:
                msg = "choices not support 'in' operator"
                raise ParameterError(self, msg)
        self.choices = choices
        
        # Check nargs (default_nargs stores is nargs is passed)
        if nargs is None:
            nargs = 1
            self.default_nargs = True
        else:
            self.default_nargs = False
            
        if self.action == "store_true" or self.action == "store_false":
            self.nargs = 0
        else:
            if (_ori.type(nargs) is int and nargs >= 0) or nargs in ['+', '*', '?']:
                if nargs == '?':
                    if self.default is None:
                        msg = "default value not set for nargs '?'"
                        raise ParameterError(self, msg)
                    if self.const is None:
                        msg = "const value not set for nargs '?'"
                        raise ParameterError(self, msg)
                self.nargs = nargs
            else:
                msg = "not valid value for nargs"
                raise ParameterError(self, msg)
        
        # Transform help
        self.help = str(help)
        
    def __str__(self):
        return "name=%s long_name=%s dest=%s type=%s default=%s nargs=%s required=%s choices=%s action=%s section=%s" % \
            (self.name, self.long_name, self.dest, self.type, self.default, self.nargs, self.required, self.choices, self.action, self.section)


class ParameterParser(_AttributeHolder):
    """Object for parsing command line strings into Python objects.
    
    Keyword arguments:
       - prog = The name of the program (default: sys.argv[0])
       - short_description = Brief description of the program
       - description = A description of what the program does
       - epilog = Text at the end of help
       - add_help = Add a -h/--help option to the parser (default: True)
    """
    
    def __init__(self,
                 prog=None,
                 short_description=None,
                 description=None,
                 bugs=None,
                 epilog=None,
                 add_help=True,
                 version=None):
        
        if prog is None:
            prog = _os.path.basename(_sys.argv[0])
            
        self.prog = prog
        self.short_description = short_description
        self.description = description
        self.bugs = bugs
        self.epilog = epilog
        self.add_help = add_help
        self.version = version
        
        # Store parameter objects
        self.parameters = []
        
        # Store the short name of the parameters introduced by the user (for an easier checking restrictions)
        self.user_name_parameters = []
        
        # Store the dependency params restrictions as a dictionary of _Parameter.names (_Parameter.name: list of _Parameter.names)
        self.dependency_params_restrictions = {}
        
        # Store incompatible params restrictions as a dictionary of _Parameter.names (_Parameter.name: list of _Parameter.names)
        self.incompatible_params_restrictions = {}
        
        if self.add_help:
            self.add_parameter('-h', '--help',
                               action='help',
                               default=SUPPRESS,
                               help='Show this help and exit')

        if self.version is not None:
            self.add_parameter('-V', '--version',
                               action='version',
                               default=SUPPRESS,
                               help='Show the version and exit')
    
    
    # ================================
    # Pretty __repr__ methods
    # Inherited from _AttributeHolder
    # ================================
    def _get_kwargs(self):
        names = [
            'prog',
            'short_description',
            'description',
            'epilog'
        ]
        return [(name, getattr(self, name)) for name in names]
    
    # ================================
    # Parameter methods
    # ================================
    def add_parameter(self, short_command, long_command=None, **kwargs):
        try:
            # Checking short_command
            if short_command is not None and  _re.match('^-[a-zA-Z]$', short_command) is not None:
                short_command = short_command.replace('-', '', 1)
                for param in self.parameters:
                    if param.name == short_command:
                        msg = "'%s' duplicated as short command" % (short_command)
                        raise ParameterError(None, msg)
            else:
                msg = "'%s' is not valid as short command" % (short_command)
                raise ParameterError(None, msg)
        
            # Checking long_command
            if long_command is not None:
                if _re.match('^--[A-Za-z]{2,}[A-Za-z_]*[A-Za-z]$', long_command) is not None:
                    long_command = long_command.replace('--', '', 1)
                    for param in self.parameters:
                        if param.long_name == long_command:
                            msg = "' %s' duplicate as long command" % (long_command)
                            raise ParameterError(None, msg)
                else:
                    msg = "'%s' is not valid as long command" % (long_command)
                    raise ParameterError(None, msg)
        
            # Checking dest
            if 'dest' in kwargs:
                dest = kwargs['dest']
                del kwargs['dest']
            else:
                if long_command is not None:
                    dest = long_command
                else:
                    dest = short_command
            for param in self.parameters:
                if dest == param.dest:
                    msg = "'%s' duplicate as dest" % (dest)
                    raise ParameterError(None, msg)
        
            new_parameter = _Parameter(short_command, long_command, dest, **kwargs)
            self.parameters.append(new_parameter)
        
        except ParameterError:
            err = _sys.exc_info()[1]
            self._error(err)
    
    # ================================
    # Parameter methods - Restrictions
    # ================================
    def dependency_params(self, *args):
        try:
            if _ori.len(args) < 2:
                msg = "dependency_params method: it needs two parameters at least"
                raise ParameterError(None, msg)
            
            # Check last parameters
            restriction = args[-1]
            if _ori.type(restriction) is str:
                r = restriction.replace('-', '', 1)
                if not self._valid_parameter("short", r):
                    msg = "dependency_params method: '-%s' not exists" % (r)
                    raise ParameterError(None, msg)
                restriction = [restriction]
            elif _ori.type(restriction) is list:
                for r in restriction:
                    r = r.replace('-', '', 1)
                    if not self._valid_parameter("short", r):
                        msg = "dependency_params method: '-%s' not exists" % (r)
                        raise ParameterError(None, msg)
            else:
                msg = "dependency_params method: '%s' must be a str or list type" % (restriction)
                raise ParameterError(None, msg)
            
            # Checking first parameters
            for p in args[:_ori.len(args)-1]:
                if _ori.type(p) is not str:
                    msg = "dependency_params method: '%s' must be a str type" % (p)
                    raise ParameterError(None, msg)
                p_replace = p.replace('-', '', 1)
                if not self._valid_parameter("short", p_replace):
                    msg = "dependency_params method: '-%s' not exists" % (p_replace)
                    raise ParameterError(None, msg)
                # Restriction cannot be a restriction to itself
                if p in restriction:
                    msg = "dependency_params method: '%s' cannot be a restriction to itself" % (p)
                    raise ParameterError(None, msg)
                # Check if there is a restriction on the same param in incompatible_params_restrictions
                # If not, create restriction in dependency_params_restrictions
                if self.incompatible_params_restrictions.has_key(p):
                    for r in restriction:
                        if r in self.incompatible_params_restrictions[p]:
                            msg = "dependency_params method: '%s' cannot be a dependency and incompatibility to the same param %s" % (p, r)
                            raise ParameterError(None, msg)
                if self.dependency_params_restrictions.has_key(p):
                    for r in restriction:
                        self.dependency_params_restrictions[p].append(r)
                else:
                    self.dependency_params_restrictions[p] = restriction
                
            # Remove duplicate values in each key
            for key, value in self.dependency_params_restrictions.iteritems():
                self.dependency_params_restrictions[key] = list(set(value))
            
            return None
        
        except ParameterError:
            err = _sys.exc_info()[1]
            self._error(err)
            
    def incompatible_params(self, *args):
        try:
            if _ori.len(args) < 2:
                msg = "incompatible_params method: it needs two parameters at least"
                raise ParameterError(None, msg)
            
            # Check last parameters
            restriction = args[-1]
            if _ori.type(restriction) is str:
                r = restriction.replace('-', '', 1)
                if not self._valid_parameter("short", r):
                    msg = "incompatible_params method: '-%s' not exists" % (r)
                    raise ParameterError(None, msg)
                restriction = [restriction]
            elif _ori.type(restriction) is list:
                for r in restriction:
                    r = r.replace('-', '', 1)
                    if not self._valid_parameter("short", r):
                        msg = "incompatible_params method: '-%s' not exists" % (r)
                        raise ParameterError(None, msg)
            else:
                msg = "incompatible_params method: '%s' must be a str or list type" % (restriction)
                raise ParameterError(None, msg)
            
            # Checking first parameters
            for p in args[:_ori.len(args)-1]:
                if _ori.type(p) is not str:
                    msg = "incompatible_params method: '%s' must be a str type" % (p)
                    raise ParameterError(None, msg)
                p_replace = p.replace('-', '', 1)
                if not self._valid_parameter("short", p_replace):
                    msg = "incompatible_params method: '-%s' not exists" % (p_replace)
                    raise ParameterError(None, msg)
                # Restriction cannot be a restriction to itself
                if p in restriction:
                    msg = "incompatible_params method: '%s' cannot be a restriction to itself" % (p)
                    raise ParameterError(None, msg)
                # Check if there is a restriction on the same param in dependency_params_restrictions
                # If not, create restriction in incompatible_params_restrictions
                if self.dependency_params_restrictions.has_key(p):
                    for r in restriction:
                        if r in self.dependency_params_restrictions[p]:
                            msg = "incompatible_params method: '%s' cannot be a dependency and incompatibility to the same param %s" % (p, r)
                            raise ParameterError(None, msg)
                if self.incompatible_params_restrictions.has_key(p):
                    for r in restriction:
                        self.incompatible_params_restrictions[p].append(r)
                else:
                    self.incompatible_params_restrictions[p] = restriction
                
            # Remove duplicate values in each key
            for key, value in self.incompatible_params_restrictions.iteritems():
                self.incompatible_params_restrictions[key] = list(set(value))
            
            return None
        
        except ParameterError:
            err = _sys.exc_info()[1]
            self._error(err)
    
    def _show_store_parameters(self):
        i = 0
        for x in self.parameters:
            i += 1
            print "Param %s -> %s" % (i, x)
    
    # ================================
    # Parser method
    # ================================
    def parse_params(self, args=None, namespace=None):
        try:
            if args is None:
                args = _sys.argv[1:]
        
            if namespace is None:
                namespace = Namespace()
        
            # Main loop
            args_len = len(args)
            index = 0
            while index < args_len:
                checking_param = args[index]
                # Validation
                if _re.match('^-[A-Za-z]+$', checking_param) is not None:
                    checking_param = checking_param.replace('-', '', 1)
                    for p in checking_param:
                        validated_param = self._valid_parameter("short", p)
                        if validated_param:
                            self.user_name_parameters.append(validated_param.name)
                            index = self._do_action(validated_param, namespace, index, args)
                        else:
                            msg = "'-%s' not a valid parameter" % (p)
                            raise ParameterError(None, msg)
                
                elif _re.match('^--[A-Za-z]{2,}[A-Za-z_]*[A-Za-z]$', checking_param):
                    # If long parameter, check if it is valid
                    checking_param = checking_param.replace('--', '', 1)
                    validated_param = self._valid_parameter("long", checking_param)
                    if validated_param:
                        self.user_name_parameters.append(validated_param.name)
                        index = self._do_action(validated_param, namespace, index, args)
                    else:
                        msg = "'--%s' not valid parameter" % (checking_param)
                        raise ParameterError(None, msg)
                else:
                    msg = "'%s' not a valid parameter format" % (checking_param)
                    raise ParameterError(None, msg)
            
                index += 1
        
            # Check if missing required parameters (in add_parameter option)
            missing_required_param_list = self._check_required_param(namespace)
            if len(missing_required_param_list) != 0:
                mpl = []
                for mp in missing_required_param_list:
                    mpl.append(mp.dest)
                msg = "missing required parameters %s" % (mpl)
                raise ParameterError(None, msg)
            
            # First check incompatible_params_restrictions
            for value, restrictions in self.incompatible_params_restrictions.iteritems():
                value = value.replace('-', '', 1)
                if value in self.user_name_parameters:
                    result = [i for i in restrictions if i.replace('-', '', 1) in self.user_name_parameters]
                    if _ori.len(result) != 0:
                        msg = "incompatible parameters %s" % (result)
                        raise ParameterError(self._valid_parameter("short", value), msg)

            # Then check dependency_params_restrictions
            for value, restrictions in self.dependency_params_restrictions.iteritems():
                value = value.replace('-', '', 1)
                if value in self.user_name_parameters:
                    result = [i for i in restrictions if i.replace('-', '', 1) not in self.user_name_parameters]
                    if _ori.len(result) != 0:
                        msg = "missing required parameters %s" % (result)
                        raise ParameterError(self._valid_parameter("short", value), msg)

            # Complete namespace with remaining parameters with default not SUPPRESS
            self._complete_namespace(namespace)
        
            return namespace
        
        except ParameterError:
            err = _sys.exc_info()[1]
            self._error(err)
            
            
    def _valid_parameter(self, type_param, param):
        """It validates the user param against the valid program parameters
        
        It returns the valid_param if there is a match
        """
        if type_param == "short":
            for valid_param in self.parameters:
                if valid_param.name == param:
                    return valid_param
        else:
            for valid_param in self.parameters:
                if valid_param.long_name == param:
                    return valid_param
        
        return False
    
    def _do_action(self, param, namespace, external_index, args):
        """It does the param action and modify the namespace
        It can modify de index depending on param.nargs
        """
        
        # Check if the action is help or version
        if param.action == 'help':
            self._print_help()
        elif param.action == 'version':
            self._print_version()
        else:
            external_index = self._store_action(param, namespace, external_index, args)
        
        return external_index
        
    def _check_required_param(self, namespace):
        missing_parameters = []
        required_params = [p for p in self.parameters if p.required == True]
        for rp in required_params:
            for p in namespace:
                if p == rp.dest:
                    break
            else:
                missing_parameters.append(rp)
        
        return missing_parameters
    
    def _complete_namespace(self, namespace):
        for p in self.parameters:
            if p.default is not SUPPRESS:
                if p.dest not in namespace:
                    setattr(namespace, p.dest, p.default)
        return None
    
    # ================
    # Actions methods
    # ================
    def _store_action(self, param, namespace, external_index, args):
        # Check if param is already store
        for ns in namespace:
            if ns == param.dest:
                msg = "passed more than one time"
                raise ParameterError(param, msg)
        
        if param.action == "store_true":
            setattr(namespace, param.dest, True)
        elif param.action == "store_false":
            setattr(namespace, param.dest, False)
        else:
            if type(param.nargs) is int:
                largs = args[external_index+1:external_index+1+param.nargs]
                external_index += param.nargs
                list_values = _parse_list(param, largs)
                if len(list_values) is 1:
                    setattr(namespace, param.dest, list_values[0])
                else:
                    setattr(namespace, param.dest, list_values)
            else:
                largs = []
                if param.nargs == '?':
                    if len(args) != external_index+1:
                        if _check_type(int, args[external_index+1]) or not args[external_index+1].startswith('-'):
                            largs.append(args[external_index+1])
                            external_index += 1
                        else:
                            # Take const
                            largs.append(param.const)
                    else:
                        # Take const
                        largs.append(param.const)
                    list_values = _parse_list(param, largs)
                else:
                    for a in args[external_index+1:]:
                        if _check_type(int, a) or not a.startswith('-'):
                            largs.append(a)
                        else:
                            break
                    external_index += len(largs)
                    list_values = _parse_list(param, largs)
                    if param.nargs == '+':
                        if len(list_values) == 0:
                            msg = "need at least one value"
                            raise ParameterError(param, msg)
                
                if param.default_nargs:
                    setattr(namespace, param.dest, list_values[0])
                else:
                    setattr(namespace, param.dest, list_values)
        
        return external_index
    
    def _print_help(self):
        # Copy self.parameters and sort it
        param_help = []
        for x in self.parameters:
            param_help.append(_copy.copy(x))
        param_help.sort(key=lambda param: param.name)
            
        sections_list = []
        separator = '\n'
        
        # Name section
        name_section = "NAME\n"
        name_section += ' ' * 7 + self.prog
        if self.short_description is not None:
            name_section += ' - ' + self.short_description
        name_section += '\n'
        sections_list.append(name_section)
        
        # Description section
        tab_description_section = ' ' * 7
        description_section = "DESCRIPTION\n"
        if self.description is not None:
            description_section += tab_description_section + self.description.replace('\n', '\n' + tab_description_section) + '\n'

        description_section += self._info_subsection_help(param_help, tab_description_section) + self._subsections_help(param_help, tab_description_section)

        sections_list.append(description_section)
        
        # Reporting bugs section
        if self.bugs is not None:
            reporting_bugs_section = "REPORTING BUGS\n"
            reporting_bugs_section += ' ' * 7 + "Report bugs to " + self.bugs + '\n'
            sections_list.append(reporting_bugs_section)
        
        # Epilog section
        if self.epilog is not None:
            sections_list.append(self.epilog)
        
        # Join all sections and print
        formated_help = separator.join(sections_list)
        self._print_message('\n' + formated_help + '\n', _sys.stdout)
        self._exit()
    
        
    def _info_subsection_help(self, param_list, actual_tab):
        if self.add_help is True or self.version is not None: 
            param_tab = actual_tab + ' ' * 3
            param_help_tab = param_tab + ' ' * 3
            
            info_help = '\n' + actual_tab + 'Info:\n'
            
            # If version exist
            if self.version is not None:
                for p in param_list:
                    if p.name == 'V':
                        version_param = p
                        param_list.remove(p)
                        break
                info_help += param_tab + '-' + version_param.name + ', --' + version_param.long_name + '\n'
                info_help += param_help_tab + version_param.help + '\n\n'
            
            # If help exist
            if self.add_help is True:
                for p in param_list:
                    if p.name == 'h':
                        help_param = p
                        param_list.remove(p)
                        break
                info_help += param_tab + '-' + help_param.name + ', --' + help_param.long_name + '\n'
                info_help += param_help_tab + help_param.help + '\n'
        
        return info_help if 'info_help' in locals() else ''
    
    def _subsections_help(self, param_list, actual_tab):
        param_tab = actual_tab + ' ' * 3
        param_help_tab = param_tab + ' ' * 3
        
        # Order subsections
        subsections = sorted(set([p.section for p in param_list]))
        
        if "Others" in subsections:
            subsections.remove("Others")
            subsections.insert(0, "Others")
        
        subsections_help = ''
        for subsection in subsections:
            subsections_help += '\n' + actual_tab + '%s:' % (subsection)
            for p in param_list:
                if p.section == subsection:
                    if p.help != SUPPRESS:
                        subsections_help += '\n'
                        subsections_help += param_tab + '-' + p.name + ', --' + p.long_name
                        p_choices = ''
                        if p.choices is not None:
                            p_choices = "choices: "
                            p_choices += str(p.choices)
                        if p.nargs == '?':
                            if p_choices is not '':
                                p_choices += ', '
                            subsections_help += ' [' + p.dest.upper() + '] (' + p_choices + 'default: ' + str(p.default) + ', const: ' + str(p.const) + ')\n'
                        elif p.nargs == '+':
                            if p_choices is not '':
                                p_choices = ' (' + p_choices + ')'
                            subsections_help += ' <' + p.dest.upper() + '> [' + p.dest.upper() + ' ...]' + p_choices + '\n'
                        elif p.nargs == 0:
                            subsections_help += '\n'
                        elif p.nargs == 1:
                            if p_choices is not '':
                                p_choices = ' (' + p_choices + ')'
                            subsections_help += ' <' + p.dest.upper() + '>' + p_choices + '\n'
                        else:
                            if p_choices is not '':
                                p_choices = ', ' + p_choices
                            subsections_help += ' <' + p.dest.upper() + ' ...> (num: ' + str(p.nargs) + p_choices + ')\n'
                        subsections_help += param_help_tab + p.help.replace('\n', '\n' + param_help_tab) + '\n'
        
        return subsections_help
        
    def _print_version(self):
        print "%s %s" % (self.prog, self.version)
        self._exit()
    
    def _print_message(self, message, file):
        if message:
            file.write(message)
    
    # ================
    # Exit and error
    # ================
    def _exit(self, status=0, message=None):
        if message:
            self._print_message(message, _sys.stderr)
        _sys.exit(status)
    
    def _error(self, message):
        """error(message: string)

        Incorporating the message to stderr and exits.
        """
        self._exit(2, ('%s: error: %s\n') % (self.prog, message))
        
    def throw_error(self, message):
        """This function allows the user to throw an error inside the parser
        """
        self._error(message)

