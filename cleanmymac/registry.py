#
# author: Cosmin Basca
#
# Copyright 2015 Cosmin Basca
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from cleanmymac.log import debug, error
from cleanmymac.constants import TARGET_ENTRY_POINT, VALID_TARGET_TYPES, TYPE_TARGET_CMD, TYPE_TARGET_DIR
from cleanmymac.schema import validate_yaml_target
from cleanmymac.target import Target, YamlShellCommandTarget, YamlDirTarget
from pkg_resources import iter_entry_points
from cleanmymac.util import yaml_files
from functools import partial
from yaml import load
import os


BUILTIN_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), 'builtins')

__TARGETS__ = {}
__YAML_TYPES__ = {
    TYPE_TARGET_CMD: YamlShellCommandTarget,
    TYPE_TARGET_DIR: YamlDirTarget
}


def load_target(yaml_file, config, update=False, verbose=False):
    with open(yaml_file, 'r+') as DESC:
        description = load(DESC)
        description = validate_yaml_target(description)
        _type = description['type']
        if _type not in VALID_TARGET_TYPES:
            error('unknown yaml target type: "{0}", valid options are: {1}'.format(
                    _type, VALID_TARGET_TYPES
            ))
            return None

        target_class = __YAML_TYPES__[_type]
        if not issubclass(target_class, Target):
            error('expected a subclass of Target for "{0}", instead got: "{1}"'.format(
                    os.path.basename(yaml_file), target_class
            ))
            return None

        if not config:
            config = {}
        config['args'] = description['args']
        return target_class(config, update=update, verbose=verbose)


def register_target(name, target):
    global __TARGETS__
    if issubclass(target, Target):
        debug('registering : {0}'.format(name))
        __TARGETS__[name] = target
    else:
        error('target {0} is not of type Target, instead got: {1}'.format(name, target))


def register_yaml_targets(path):
    global __TARGETS__
    for name, yaml_file in yaml_files(path):
        debug('registering : {0}'.format(name))
        __TARGETS__[name] = partial(load_target, yaml_file)


def get_target(name):
    global __TARGETS__
    try:
        return __TARGETS__[name]
    except KeyError:
        error("no target found for: {0}".format(name))
        return None


def iter_targets():
    global __TARGETS__
    for name, target in __TARGETS__.iteritems():
        yield name, target


# register built in targets
# 1 YAML based ones
register_yaml_targets(BUILTIN_REGISTRY_PATH)

# register installed targets (if any)
debug("looking for registered cleanup targets...")
for ep in iter_entry_points(TARGET_ENTRY_POINT):
    debug("found: {0}".format(ep))