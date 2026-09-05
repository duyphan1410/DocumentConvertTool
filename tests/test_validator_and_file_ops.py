import os
import tempfile
import zipfile


from src.core.validator import validate_archive_file
from src.utils.file_ops import validate_move_operation


def test_validate_archive_file_empty_path():
    is_valid, msg = validate_archive_file("")
    assert not is_valid
    assert len(msg) > 0


def test_validate_archive_file_not_found():
    is_valid, msg = validate_archive_file("C:/non_existent_folder_xyz/fake.zip")
    assert not is_valid
    assert "fake.zip" in msg or "không tồn tại" in msg or "not exist" in msg.lower()


def test_validate_archive_file_unsupported_ext():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        tf.write(b"Hello world")
        tf_path = tf.name

    try:
        is_valid, msg = validate_archive_file(tf_path)
        assert not is_valid
        assert ".txt" in msg
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_validate_archive_file_valid_zip():
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
        tf_path = tf.name

    try:
        with zipfile.ZipFile(tf_path, "w") as zf:
            zf.writestr("test.md", "# Test Heading\nHello")

        is_valid, msg = validate_archive_file(tf_path)
        assert is_valid
        assert msg == ""
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_validate_move_operation_valid():
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_file = os.path.join(tmp_dir, "doc.md")
        with open(src_file, "w") as f:
            f.write("content")

        sub_dir = os.path.join(tmp_dir, "subfolder")
        os.makedirs(sub_dir, exist_ok=True)

        is_valid, msg = validate_move_operation(src_file, sub_dir)
        assert is_valid
        assert msg == ""


def test_validate_move_operation_same_parent():
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_file = os.path.join(tmp_dir, "doc.md")
        with open(src_file, "w") as f:
            f.write("content")

        # Moving to its current parent directory should be rejected
        is_valid, msg = validate_move_operation(src_file, tmp_dir)
        assert not is_valid


def test_validate_move_operation_circular_parent_into_child():
    with tempfile.TemporaryDirectory() as tmp_dir:
        parent_dir = os.path.join(tmp_dir, "parent")
        child_dir = os.path.join(parent_dir, "child")
        os.makedirs(child_dir, exist_ok=True)

        # Moving parent into its own child directory is illegal
        is_valid, msg = validate_move_operation(parent_dir, child_dir)
        assert not is_valid


def test_validate_move_operation_collision():
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_file = os.path.join(tmp_dir, "doc.md")
        with open(src_file, "w") as f:
            f.write("content 1")

        sub_dir = os.path.join(tmp_dir, "subfolder")
        os.makedirs(sub_dir, exist_ok=True)

        existing_file = os.path.join(sub_dir, "doc.md")
        with open(existing_file, "w") as f:
            f.write("content 2")

        is_valid, msg = validate_move_operation(src_file, sub_dir)
        assert not is_valid
        assert "doc.md" in msg
