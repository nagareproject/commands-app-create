# --
# Copyright (c) 2008-2018 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import os
import tempfile
from copy import copy

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

import yaml
import configobj
from nagare.admin import admin
from nagare.services import plugins
from cookiecutter import main, exceptions, log


class Templates(plugins.Plugins):
    ENTRY_POINTS = 'nagare.templates'

    def __init__(self):
        super(Templates, self).__init__({})

    def load_activated_plugins(self, activations=None):
        templates = super(Templates, self).load_activated_plugins(activations)

        aliases = []
        for entry, template in templates:
            for name in template.names:
                entry = copy(entry)
                entry.name = name
                aliases.append((entry, template))

        return sorted(templates + aliases, key=lambda template: self.load_order(template[1]))


class Create(admin.Command):
    DESC = 'Create an application structure'
    WITH_CONFIG_FILENAME = False

    def set_arguments(self, parser):
        parser.add_argument('-l', '--list', action='store_true', help='list the available templates')
        parser.add_argument('template', default='default', nargs='?', help='template to use')
        parser.add_argument('path', default='', nargs='?', help='path into the template directory')

        parser.add_argument('--no-input', action='store_true', help="don't prompt the user; use default settings")
        parser.add_argument('--checkout', help='the branch, tag or commit ID to checkout after clone')
        parser.add_argument('-v', '--verbose', action='store_true', help='print debug information')
        parser.add_argument(
            '-r', '--replay', action='store_true',
            help='Do not prompt for parameters and only use information entered previously'
        )
        parser.add_argument('-o', '--output-dir', default='', help='directory where to generate the project into')
        parser.add_argument(
            '-f', '--overwrite', action='store_true',
            help="overwrite the contents of the output directory if it already exists"
        )

        super(Create, self).set_arguments(parser)

    def list(self, template, **config):
        templates = Templates()

        if not templates:
            print('No registered templates')
            return 0

        default = templates.pop('default', None)

        if template and (template in templates):
            templates = {template: templates[template]}

        padding = len(max(templates, key=len))

        print('Available templates:')
        for name in sorted(templates):
            print(' - %s:%s' % (name.ljust(padding), templates[name].DESC))

        if default is not None:
            print('')
            print(' * default: ' + default.DESC)

        return 0

    def create(self, template, path, verbose, overwrite, **config):
        path = path.lstrip(os.sep)
        url = urlparse.urlsplit(template)

        if not url.scheme:
            if (os.sep not in template) and not os.path.exists(template):
                templates = Templates()
                if template not in templates:
                    print("Template '%s' not found" % template)
                    return 1

                template = templates[template].path
                if path:
                    template = os.path.join(template, path)

        log.configure_logger('DEBUG' if verbose else 'INFO')

        def remove_empty(d):
            return {k: remove_empty(v) for k, v in d.items() if remove_empty(v)} if isinstance(d, dict) else d

        with tempfile.NamedTemporaryFile() as cc_yaml_config:
            has_user_data_file, user_data_file = self.get_user_data_file()

            cc_config = configobj.ConfigObj(user_data_file).dict().get('cookiecutter', {}) if has_user_data_file else {}
            cc_config = remove_empty(cc_config)

            cc_yaml_config.write(yaml.dump(cc_config, default_flow_style=False).encode('utf-8'))
            cc_yaml_config.flush()

            cc_yaml_config_name = cc_yaml_config.name if cc_config else None

            try:
                main.cookiecutter(
                    template,
                    overwrite_if_exists=overwrite, config_file=cc_yaml_config_name,
                    **config
                )
            except exceptions.RepositoryNotFound as e:
                if not url.scheme or not path:
                    raise

                repo_dir = e.args[0].splitlines()[-1]
                template = os.path.basename(repo_dir)
                main.cookiecutter(
                    os.path.join(template, path),
                    overwrite_if_exists=overwrite, config_file=cc_yaml_config_name,
                    **config
                )

        return 0

    def run(self, list, **config):
        try:
            status = (self.list if list else self.create)(**config)
        except Exception as e:
            if e.args:
                print(e.args[0])
            status = 1

        return status
