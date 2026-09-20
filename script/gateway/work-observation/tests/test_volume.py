from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
import volume


class VolumeSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
    def tearDown(self):self.tmp.cleanup()
    def test_existing_or_nested_paths_never_reach_mkfs(self):
        for directory,mount in [(self.root,self.root/'mount'),(self.root/'image',self.root),
                                (self.root/'image',self.root/'image/mount')]:
            with patch.object(volume,'run') as run:
                with self.assertRaises(ValueError):volume.create(directory,mount)
                run.assert_not_called()
    def test_symlink_and_small_volume_outside_lab_refused(self):
        link=self.root/'link';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):volume.private_path(link/'child')
        with patch.object(volume,'run') as run:
            with self.assertRaises(ValueError):volume.create(self.root/'image',self.root/'mount',True)
            run.assert_not_called()
    def test_nonempty_mountpoint_not_hidden_by_mount(self):
        target=self.root/'mount';target.mkdir();(target/'user-file').write_text('preserve')
        with patch.object(volume,'inspect',return_value={'mounted':False}),patch.object(volume,'run') as run:
            with self.assertRaises(ValueError):volume.attach({'mountpoint':str(target),'image':str(self.root/'image')})
            run.assert_not_called()
        self.assertEqual((target/'user-file').read_text(),'preserve')
    def test_unrelated_mount_cannot_be_detached_or_adopted(self):
        target=self.root/'mount';target.mkdir()
        result={'filesystems':[{'target':str(target),'source':'/dev/sda1','fstype':'ext4','options':'rw,nodev,nosuid,noexec'}]}
        with patch.object(volume,'run',return_value=json.dumps(result)):
            with self.assertRaises(ValueError):volume.inspect({'mountpoint':str(target)})
    def test_failed_post_mount_validation_unmounts_only_new_mount(self):
        target=self.root/'mount';target.mkdir()
        with patch.object(volume,'inspect',side_effect=[{'mounted':False},ValueError('fixture')]),patch.object(volume,'run') as run:
            with self.assertRaises(ValueError):volume.attach({'mountpoint':str(target),'image':str(self.root/'image')})
            self.assertEqual(run.call_args_list[-1].args,('umount',str(target)))


if __name__=='__main__':unittest.main()
