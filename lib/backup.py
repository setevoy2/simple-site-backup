#!/usr/bin/env python


import os
import tarfile
import datetime
import subprocess
import configparser


from lib import common
from lib import s3sync


def www_backup(site, www_backup_file, parser):

    # if 'www_data_path' doesn't set in config for $site - skip it
    try:
        www_source_dir = common.set_params(parser, site).get('www_data_path')
    except configparser.NoOptionError as e:
        print('\nWARNING: {}.\nSkipping WWW backup for the {}.\n'.format(e, site))
        return

    print('\nCreating WWW backup for:\nsite: {}\nfrom: {}\nto: {}'.format(site, www_source_dir, www_backup_file))

    with tarfile.open(www_backup_file, "w:gz") as tar:
        tar.add(www_source_dir, arcname=os.path.basename(www_source_dir))

    print('\nWWW backup done.\n')


def db_backup(site, db_backup_file, parser):

    # if 'mysql_*' doesn't set in config for $site - skip it
    try:
        mysql_host = parser.get(site, 'mysql_host')
        mysql_db = parser.get(site, 'mysql_db')
        mysql_user = parser.get(site, 'mysql_user')
        mysql_pass = parser.get(site, 'mysql_pass')
    except configparser.NoOptionError as e:
        print('\nWARNING: {}.\nSkipping DB backup for the {}.\n'.format(e, site))
        return

    print ('Creating DB backup for:\n'
           'site: {}\n'
           'host: {}\n'
           'database: {}\n'
           'user: {}\n'
           'to: {}'.format(site, mysql_host, mysql_db, mysql_user, db_backup_file))

    dump_cmd = ['mysqldump ' +
                '--user={mysql_user} '.format(mysql_user=mysql_user) +
                '--password={db_pw} '.format(db_pw=mysql_pass) +
                '--host={db_host} '.format(db_host=mysql_host) +
                '{db_name} '.format(db_name=mysql_db) +
                '> ' +
                '{filepath}'.format(filepath=db_backup_file)]

    dump = subprocess.Popen(dump_cmd, shell=True)
    dump.wait()

    print('\nDB backup done.\n')


def backup(config):

    # create parser object to pass to functions
    parser = common.get_config(config)

    # set own settings
    settings = common.set_params(parser, 'backup-settings')
    # "/backups"
    backup_root_path = settings.get('backup_root_path')
    # "/backups" + "files"
    files_destination_dir = os.path.join(backup_root_path, settings.get('backup_files_path'))
    # "/backups" + "databases"
    db_destination_dir = os.path.join(backup_root_path, settings.get('backup_db_path'))

    print('\nGot own settings:\n\n'
          'backup_root_path = {}\n'
          'backup_files_path = {}\n'
          'backup_db_path = {}\n'
          .format(backup_root_path, files_destination_dir, db_destination_dir)
         )

    # check for backup directories, create if not
    common.check_dirs([backup_root_path, files_destination_dir, db_destination_dir])

    # day - month - year - hours - minutes
    # 02-01-2018-13-58
    today = datetime.datetime.now().strftime('%d-%m-%Y-%H-%M')

    # start sites backup here
    # for [backup-settings], [test], [rtfm]
    for site in parser.sections():
        # skip own settings section 'backup-settings' and 'defaults'
        if all ([site != 'backup-settings', site != 'defaults']):

            # check for S3 sync first
            # if section/site have 's3_sync' = True then check and install dependencies
            # False otherwise
            try:
                parser.get(site, 's3_sync')
                common.check_deps()
            except configparser.NoOptionError:
                pass

            # WWW backup section
            # /backups/files/test-02-01-2018-13-58.gz
            www_backup_file = os.path.join(files_destination_dir,
                                           today + '_'+ site + '_' + '.gz')
            # exec www files tar
            www_backup(site, www_backup_file, parser)

            # DB backup section
            # /backups/databases/example_bkp_test-02-01-2018-15-59.sql
            db_backup_file = os.path.join(db_destination_dir,
                                          today + '_' + site + '_' + parser.get(site, 'mysql_db') + '.sql')

            # exec mysql database dump
            db_backup(site, db_backup_file, parser)

            # AWS S3 upload section
            # testing, #Todo
            #s3sync.upload(site, [www_backup_file, db_backup_file], parser)

            # Cleanup section
            # delete files older then "bkps_keep_days" param
            common.bkps_cleanup(site, [files_destination_dir, db_destination_dir], parser)