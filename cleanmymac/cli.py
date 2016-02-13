# coding=utf-8
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
import click
import click_log
import os
from yaml import load
from time import sleep

from cleanmymac.__version__ import str_version
from cleanmymac.log import info, warn, error, debug, echo_warn, echo_info
from cleanmymac.registry import iter_targets, register_yaml_targets
from cleanmymac.schema import validate_yaml_config
from cleanmymac.target import Target
from cleanmymac.util import get_disk_usage
from cleanmymac.constants import UNIT_MB, PROGRESSBAR_ADVANCE_DELAY

__author__ = 'cosmin'


def get_options(path=None):
    """
    Return the global configuration options. This method also expands the user home folder
    specified by '~'. In addition, the yaml config file is validated after parse.
    If the path is not specified, the ~/.cleanmymac.yaml configuration file is looked up, if not
    found, the global configuration is set to an empty dict.

    :param path: optional path to a yaml configuration file
    :type path: str
    :return: a python object containing the actual configuration
    :rtype: dict
    """
    cfg = {}
    if not path:
        path = os.path.join(os.path.expanduser('~'), '.cleanmymac.yaml')
    path = os.path.abspath(path)
    if not os.path.exists(path):
        warn('global configuration file not found, proceeding without.')
    else:
        with open(path, 'r+') as cfg:
            cfg = load(cfg)
    return validate_yaml_config(cfg)


def _config_targets_path(config):
    if 'cleanmymac' in config:
        if 'targets_path' in config['cleanmymac']:
            return config['cleanmymac']['targets_path']
    return []


@click.command(name='cleanmymac', context_settings={
    'help_option_names': ['-h', '--help']
})
@click_log.init()
@click_log.simple_verbosity_option('-L', '--log-level', default='INFO')
@click.option('-u', '--update', is_flag=True, help='update the target if applicable')
@click.option('-d', '--dry_run', is_flag=True, help='describe the actions to be performed, do not execute them')
@click.option('-q', '--quiet', is_flag=True, help='run in quiet mode')
@click.option('-l', '--list', 'list_targets', is_flag=True, help='list registered cleanup targets')
@click.option('-s', '--stop_on_error', is_flag=True, help='stop execution when first error is detected')
@click.option('-c', '--config', default=None, envvar='CLEANMYMAC_CONFIG', help='specify the configuration path')
@click.option('-t', '--targets_path', default=None, type=click.Path(exists=True), multiple=True,
              help='specify extra yaml defined targets path')
@click.version_option(version=str_version)
@click.argument('targets', metavar='TARGETS', type=str, nargs=-1)
@click.pass_context
def cli(ctx, update, dry_run, quiet, list_targets, stop_on_error, config, targets_path, targets, **kwargs):
    """
    the main **run** method, responsible for creating the parser and executing the main logic in
    **cleanmymac**

    :param ctx:  the click context
    :type ctx: :class:`click.Context`
    :param bool update: perform update of targets (if applicable)
    :param dry_run: do not execute the actions, but log the result
    :param quiet: quiet mode (no output), show a progressbar instead
    :param list_targets: list the installed targets
    :param stop_on_error: abort the execution on first error
    :param config: the configuration path
    :param targets_path: extra targets paths
    :param targets: the targets
    """
    all_targets = dict(iter_targets())

    verbose = not quiet
    if targets:
        target_names = set(targets)
    else:
        target_names = set(all_targets.keys())

    log_message = echo_info if verbose else lambda msg: msg
    log_message('found {0} registered cleanup targets'.format(len(all_targets)))

    config = get_options(path=config)
    # register extra targets if any
    for pth in _config_targets_path(config):
        register_yaml_targets(pth)
    if targets_path and os.path.isdir(targets_path):
        register_yaml_targets(targets_path)

    if list_targets:
        for name, target_initializer in all_targets.items():
            echo_warn(' > {0}'.format(name))
    else:
        with click.progressbar(all_targets.items(), label='Processing cleanup targets:', width=40) as all_targets_bar:
            free_space_before = get_disk_usage('/', unit=UNIT_MB).free
            if verbose:
                targets_to_process = all_targets.items()
            else:
                targets_to_process = all_targets_bar

            for name, target_initializer in targets_to_process:
                if name not in target_names:
                    continue
                log_message('\ncleaning: {0}'.format(name.upper()))
                target_cfg = config[name] if name in config else None
                target = target_initializer(target_cfg, update=update, verbose=verbose)

                if not isinstance(target, Target):
                    error('expected an instance of Target, instead got: {0}'.format(target))
                    continue

                if dry_run:
                    echo_warn(target.describe())
                else:
                    try:
                        target()
                    except Exception, ex:
                        error('could not cleanup target "{0}". Reason:\n{1}'.format(
                            name, ex))
                        if stop_on_error:
                            break

                if not verbose:
                    sleep(PROGRESSBAR_ADVANCE_DELAY)  # nicer progress bar display for fast executing targets

            free_space_after = get_disk_usage('/', unit=UNIT_MB).free
            if not dry_run:
                log_message('\ncleanup complete')
                log_message('freed {0:.3f} MB of disk space'.format(free_space_after-free_space_before))
