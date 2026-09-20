#!/usr/bin/env python3
"""Manage one dedicated, bounded capture data volume. Never format a device.

The image is created exclusively in a new private directory; mkfs receives only
that new regular file. Existing images are inspected or mounted, never formatted.
No fstab edits, filesystem remounts, request replay, or image deletion.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess

CAPACITY=200 << 30
LAB_CAPACITY=256 << 20
SCHEMA='work-observation-volume-v1'


def run(*args):
    result=subprocess.run(args,check=True,capture_output=True,text=True,timeout=120)
    return result.stdout.strip()


def private_path(value):
    path=Path(value)
    if not path.is_absolute() or '..' in path.parts or path==Path('/'):
        raise ValueError('absolute_nonroot_path_required')
    for parent in (path,*path.parents):
        if parent.is_symlink():raise ValueError('symlink_path_refused')
    return path


def create(directory,mountpoint,lab=False):
    directory,mountpoint=private_path(directory),private_path(mountpoint)
    if directory==mountpoint or directory in mountpoint.parents or mountpoint in directory.parents:
        raise ValueError('image_and_mount_must_be_separate')
    if lab and (Path('/data/work-observation-lab') not in directory.parents or Path('/data/work-observation-lab') not in mountpoint.parents):
        raise ValueError('small_test_volume_requires_isolated_lab_paths')
    if directory.exists() or mountpoint.exists():raise ValueError('create_requires_two_new_paths')
    size=LAB_CAPACITY if lab else CAPACITY
    directory.mkdir(mode=0o700,parents=False)
    mountpoint.mkdir(mode=0o700,parents=False)
    image=directory/'capture.ext4'
    fd=os.open(image,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        os.ftruncate(fd,size)
        os.fsync(fd)
    finally:os.close(fd)
    # Only a file exclusively created above, never an existing image or device.
    run('mkfs.ext4','-q','-F','-m','0','-L','work-observation',str(image))
    identity=run('blkid','-s','UUID','-o','value',str(image))
    if not re.fullmatch(r'[a-f0-9-]{36}',identity):raise ValueError('invalid_new_filesystem_identity')
    manifest={'schema':SCHEMA,'image':str(image),'mountpoint':str(mountpoint),'capacity_bytes':size,'filesystem_uuid':identity,'laboratory':lab}
    with (directory/'volume.json').open('x') as stream:
        os.chmod(stream.name,0o600);json.dump(manifest,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    return manifest


def load(directory):
    directory=private_path(directory)
    manifest_path=directory/'volume.json'
    info=manifest_path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077 or info.st_uid!=os.geteuid():
        raise ValueError('unsafe_volume_manifest')
    value=json.loads(manifest_path.read_text())
    image,mountpoint=private_path(value['image']),private_path(value['mountpoint'])
    if value.get('schema')!=SCHEMA or image!=directory/'capture.ext4':raise ValueError('unexpected_volume_image')
    expected=LAB_CAPACITY if value.get('laboratory') is True else CAPACITY
    info=image.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o077 or info.st_size!=expected or value['capacity_bytes']!=expected:
        raise ValueError('unsafe_or_resized_image')
    if run('blkid','-s','UUID','-o','value',str(image))!=value['filesystem_uuid']:
        raise ValueError('filesystem_identity_changed')
    return value


def inspect(value):
    target=Path(value['mountpoint'])
    data=json.loads(run('findmnt','--json','--target',str(target),'-o','TARGET,SOURCE,FSTYPE,OPTIONS'))
    mounts=data.get('filesystems',[])
    if len(mounts)!=1 or mounts[0]['target']!=str(target):return {'mounted':False,'verified':False}
    row=mounts[0]
    if row['fstype']!='ext4' or not re.fullmatch(r'/dev/loop\d+',row['source']):raise ValueError('unexpected_mounted_filesystem')
    if run('blkid','-s','UUID','-o','value',row['source'])!=value['filesystem_uuid']:
        raise ValueError('mounted_filesystem_identity_mismatch')
    devices=json.loads(run('losetup','--list','--json','--output','BACK-FILE',row['source']))['loopdevices']
    if len(devices)!=1 or devices[0]['back-file']!=value['image']:raise ValueError('unexpected_loop_backing_file')
    options=set(row['options'].split(','))
    if not {'rw','nodev','nosuid','noexec'}<=options:raise ValueError('unsafe_volume_mount_options')
    usage=os.statvfs(target)
    total=usage.f_blocks*usage.f_frsize
    if total>value['capacity_bytes']:raise ValueError('filesystem_capacity_exceeded')
    return {'mounted':True,'verified':True,'filesystem_bytes':total,'available_bytes':usage.f_bavail*usage.f_frsize,
        'capacity_bytes':value['capacity_bytes'],'filesystem_uuid':value['filesystem_uuid'],'laboratory':value['laboratory']}


def attach(value):
    current=inspect(value)
    if current['mounted']:return current
    target=Path(value['mountpoint'])
    if not target.is_dir() or any(target.iterdir()):raise ValueError('mountpoint_not_empty')
    # Permission zero on the underlying directory stops a non-root collector
    # from accidentally writing onto the host filesystem if this volume is absent.
    os.chmod(target,0o000)
    run('mount','-o','loop,nodev,nosuid,noexec',value['image'],str(target))
    try:
        os.chmod(target,0o700)
        return inspect(value)
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        # This mount was created by the successful command immediately above.
        # A validation failure must not leave a partially accepted lab volume.
        run('umount',str(target))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('create','attach','status','detach'))
    parser.add_argument('--directory',required=True)
    parser.add_argument('--mountpoint')
    parser.add_argument('--lab-small',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    if os.geteuid()!=0:raise SystemExit('volume_management_requires_root')
    try:
        if args.command=='create':
            if not args.mountpoint:raise ValueError('mountpoint_required')
            result=create(args.directory,args.mountpoint,args.lab_small)
        else:
            directory=private_path(args.directory)
            with (directory/'volume.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                value=load(directory)
                if args.command=='attach':result=attach(value)
                elif args.command=='status':result=inspect(value)
                else:
                    result=inspect(value)
                    if result['mounted']:run('umount',value['mountpoint'])
                    result=inspect(value)
        print(json.dumps(result,indent=2))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        raise SystemExit('volume_operation_failed; no existing filesystem formatted or image deleted')


if __name__=='__main__':main()
