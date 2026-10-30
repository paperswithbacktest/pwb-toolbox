"""The Hub loader asks the Hub once per dataset and per process, and not at all offline."""

import os
import tempfile
import unittest
from unittest import mock

import pwb_toolbox.datasets as ds


def _fake_cache(root, repo_id, sha, files):
    base = os.path.join(root, f"datasets--{repo_id.replace('/', '--')}", "snapshots", sha)
    for name in files:
        path = os.path.join(base, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"")
    return base


class HubSnapshotTest(unittest.TestCase):
    def setUp(self):
        ds._HUB_SNAPSHOTS.clear()

    def test_offline_uses_the_newest_local_snapshot_without_touching_the_hub(self):
        with tempfile.TemporaryDirectory() as root:
            _fake_cache(root, "paperswithbacktest/X", "aaa", ["data/train-2020-01.parquet"])
            newest = _fake_cache(root, "paperswithbacktest/X", "bbb", ["data/train-2020-01.parquet", "README.md"])
            os.utime(newest, None)
            with mock.patch.object(ds, "HF_HUB_CACHE", root), \
                 mock.patch.dict(os.environ, {"PWB_HF_OFFLINE": "1"}), \
                 mock.patch.object(ds, "HfApi") as api:
                sha, files = ds._hub_snapshot("paperswithbacktest/X", None)
        api.assert_not_called()
        self.assertEqual(sha, "bbb")
        self.assertEqual(files, ["README.md", "data/train-2020-01.parquet"])

    def test_online_asks_the_hub_once_then_remembers(self):
        info = mock.Mock(sha="c0ffee", siblings=[mock.Mock(rfilename="data/train-2021-01.parquet"), mock.Mock(rfilename="README.md")])
        with mock.patch.dict(os.environ, {"PWB_HF_OFFLINE": "0", "HF_HUB_OFFLINE": "0"}), \
             mock.patch.object(ds, "HfApi") as api:
            api.return_value.dataset_info.return_value = info
            first = ds._hub_snapshot("paperswithbacktest/Y", None)
            second = ds._hub_snapshot("paperswithbacktest/Y", None)
        self.assertEqual(first, ("c0ffee", ["README.md", "data/train-2021-01.parquet"]))
        self.assertIs(first, second)
        self.assertEqual(api.return_value.dataset_info.call_count, 1)

    def test_hub_failure_falls_back_to_the_local_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            _fake_cache(root, "paperswithbacktest/Z", "123", ["data/train-2019-01.parquet"])
            with mock.patch.object(ds, "HF_HUB_CACHE", root), \
                 mock.patch.dict(os.environ, {"PWB_HF_OFFLINE": "0", "HF_HUB_OFFLINE": "0"}), \
                 mock.patch.object(ds, "HfApi") as api:
                api.return_value.dataset_info.side_effect = ConnectionError("no network")
                sha, files = ds._hub_snapshot("paperswithbacktest/Z", None)
        self.assertEqual((sha, files), ("123", ["data/train-2019-01.parquet"]))

    def test_split_files_are_pinned_to_the_snapshot_revision(self):
        with mock.patch.object(ds, "_hub_snapshot", return_value=("deadbeef", ["data/train-2020-01.parquet", "data/train-2020-02.parquet"])), \
             mock.patch.object(ds, "hf_hub_download", side_effect=lambda **kw: "/tmp/" + kw["filename"].replace("/", "_")) as dl, \
             mock.patch.object(ds, "_read_parquet_files", return_value="frame") as read:
            out = ds._load_dataset_from_hf("Some-Dataset", "train", None, symbols=["AAPL"])
        self.assertEqual(out, "frame")
        self.assertEqual({call.kwargs["revision"] for call in dl.call_args_list}, {"deadbeef"})
        self.assertEqual(len(dl.call_args_list), 2)
        read.assert_called_once()


if __name__ == "__main__":
    unittest.main()
