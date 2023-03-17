# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import os
import tank
import sgtk
import glob
import re
import nukescripts

from sgtk import TankError
from hiero.ui import menuBar, findMenuAction, registerAction
import hiero as hiero
import nuke


from sgtk.platform import Application


class StgkStarterApp(Application):
    """
    The app entry point. This class is responsible for initializing and tearing down
    the application, handle menu registration etc.
    """
    app_name = "Load Playlist"
    myVersion = "v0.0"
    author = "Written by Sean Feeley"

    def init_app(self):
        """
        Called as the application is being initialized
        """

        # first, we use the special import_module command to access the app module
        # that resides inside the python folder in the app. This is where the actual UI
        # and business logic of the app is kept. By using the import_module command,
        # toolkit's code reload mechanism will work properly.
        app_payload = self.import_module("app")

        # now register a *command*, which is normally a menu entry of some kind on a Shotgun
        # menu (but it depends on the engine). The engine will manage this command and
        # whenever the user requests the command, it will call out to the callback.

        # first, set up our callback, calling out to a method inside the app module contained
        # in the python folder of the app
        menu_callback = lambda: self.loadPlaylist()

        # now register the command with the engine
        self.engine.register_command("Load Playlist...", menu_callback)

    def _get_current_project(self):
        """
        Returns the current project based on where in the UI the user clicked
        """

        # get the menu selection from hiero engine
        selection = self.engine.get_menu_selection()

        if len(selection) != 1:
            raise TankError("Please select a single Project!")

        if not isinstance(selection[0], hiero.core.Bin):
            raise TankError("Please select a Hiero Project!")

        project = selection[0].project()
        if project is None:
            # apparently bins can be without projects (child bins I think)
            raise TankError("Please select a Hiero Project!")

        return project


    def loadPlaylist(self):
        hiero_project = self._get_current_project()
        path = hiero_project.path()
        tank_instance = tank.sgtk_from_path(path)
        ctx = tank_instance.context_from_path(path)

        projects = ctx.tank.shotgun.find('Project', [['sg_status', 'is', 'active']], ['name', 'code'],
                                         order=[{'field_name': 'code', 'direction': 'asc'}])
        p = nuke.Panel(self.app_name + " " + self.myVersion)
        projects.insert(0, ctx.project)
        # projects.insert(0, {'type': 'Project', 'id': 3806, 'name': 'MRV002_TartanGFX', 'code': 'MRV002_TartanGFX'})

        p.addEnumerationPulldown('Projects:', ' '.join([d['name'] for d in projects]))
        ret = p.show()
        project_name = p.value("Projects:")
        for project in projects:
            if project['name'] == project_name:
                playlists = ctx.tank.shotgun.find('Playlist',
                                                  [['project.Project.id', 'is', project['id']]],
                                                  ['versions', 'code'],
                                                  order=[{'field_name': 'id', 'direction': 'desc'}])
                p = nuke.Panel(self.app_name + " " + self.myVersion)

                p.addEnumerationPulldown('Playlists:', ' '.join([d['code'].replace(' ', '\ ') for d in playlists]))
                ret = p.show()
                playlist_name = p.value("Playlists:")
                new_nodes = []
                working_plate_nodes = []
                for p in playlists:
                    if p['code'] == playlist_name:
                        playlistBin = hiero.core.Bin(playlist_name)
                        hiero_project.clipsBin().addItem(playlistBin)
                        playlistVersionsBin = hiero.core.Bin('Versions')
                        playlistPlatesBin = hiero.core.Bin('Plates')
                        playlistBin.addItem(playlistVersionsBin)
                        playlistBin.addItem(playlistPlatesBin)
                        for v in p['versions']:
                            self._load_version(playlistVersionsBin, v)
                            self._load_plate(playlistPlatesBin, v)
                break

    def _load_plate(self, bin, version):
        nodes = []
        app_shotgun = sgtk.platform.Application.shotgun.fget(self)
        entity = app_shotgun.find_one('Version',
                                           [['id', 'is', version['id']]],
                                           ['entity'])['entity']
        pfs = app_shotgun.find('PublishedFile',
                                         [['entity', 'is', entity],
                                          ['sg_element', 'is', 'working'],
                                          ['version.Version.sg_is_hero', 'is', True]],
                                         ['sg_publish_path',
                                          'sg_publish_last_frame',
                                          'sg_publish_first_frame',
                                          'code'],
                                         order=[{'field_name': 'id', 'direction': 'desc'}])

        for pf in pfs:
            if pf and (pf.get('sg_publish_path')):
                bin.createClip(pf['sg_publish_path']['local_path'].replace('\\', '/'))
                return
        pfs = app_shotgun.find('PublishedFile',
                                         [['entity', 'is', entity],
                                          ['version.Version.sg_is_hero', 'is', True]],
                                         ['sg_publish_path',
                                          'sg_publish_last_frame',
                                          'sg_publish_first_frame',
                                          'code'],
                                         order=[{'field_name': 'id', 'direction': 'desc'}])

        for pf in pfs:
            if pf and (pf.get('sg_publish_path')):
                bin.createClip(pf['sg_publish_path']['local_path'].replace('\\', '/'))
                return


    def _load_version(self, bin, version):
        app_shotgun = sgtk.platform.Application.shotgun.fget(self)
        pf = app_shotgun.find_one('PublishedFile',
                                       [['sg_versions_1.Version.id', 'is', version['id']]],
                                       ['sg_publish_path',
                                        'sg_publish_last_frame',
                                        'sg_publish_first_frame',
                                        'code'])
        bin.createClip(pf['sg_publish_path']['local_path'].replace('\\', '/'))