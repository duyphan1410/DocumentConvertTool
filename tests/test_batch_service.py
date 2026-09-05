import os
import shutil
import tempfile
import zipfile


from src.services.batch_service import BatchConversionService, BatchResult


def test_batch_service_scan_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create sample document structure
        os.makedirs(os.path.join(tmp_dir, "sub"), exist_ok=True)
        with open(os.path.join(tmp_dir, "doc1.md"), "w", encoding="utf-8") as f:
            f.write("# Doc 1")
        with open(os.path.join(tmp_dir, "sub", "doc2.csv"), "w", encoding="utf-8") as f:
            f.write("a,b\n1,2")
        with open(os.path.join(tmp_dir, "ignored.exe"), "w") as f:
            f.write("bin")

        service = BatchConversionService()
        files = service.scan_files_for_target(tmp_dir, ".pdf")
        assert len(files) == 2
        assert any(f.endswith("doc1.md") for f in files)
        assert any(f.endswith("doc2.csv") for f in files)
        assert not any(f.endswith("ignored.exe") for f in files)


def test_batch_service_folder_to_folder_conversion():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as out_dir:
        # Create input markdown and csv files
        with open(os.path.join(src_dir, "a.md"), "w", encoding="utf-8") as f:
            f.write("# Hello Markdown\nThis is a test.")
        with open(os.path.join(src_dir, "b.csv"), "w", encoding="utf-8") as f:
            f.write("col1,col2\nval1,val2")

        service = BatchConversionService()
        progress_records = []

        def on_prog(curr, tot, name, res):
            progress_records.append((curr, tot, name, res.status))

        res = service.run_batch(
            source_path=src_dir,
            target_ext=".html",
            output_destination=out_dir,
            output_type="folder",
            preserve_structure=True,
            on_progress=on_prog,
        )

        assert res.total == 2
        assert res.succeeded == 2
        assert res.failed == 0
        assert len(progress_records) == 2
        assert os.path.exists(os.path.join(out_dir, "a.html"))
        assert os.path.exists(os.path.join(out_dir, "b.html"))


def test_batch_service_archive_to_zip_conversion():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create input archive
        zip_input = os.path.join(tmp_dir, "input_docs.zip")
        with zipfile.ZipFile(zip_input, "w") as zf:
            zf.writestr("notes/intro.md", "# Intro\nBatch Archive Test")
            zf.writestr("data.csv", "name,score\nAlice,100")

        out_zip = os.path.join(tmp_dir, "converted.zip")

        service = BatchConversionService()
        res = service.run_batch(
            source_path=zip_input,
            target_ext=".md",
            output_destination=out_zip,
            output_type="zip",
            preserve_structure=True,
        )

        assert res.total == 2
        assert res.succeeded == 2
        assert res.failed == 0
        assert os.path.exists(out_zip)
        assert zipfile.is_zipfile(out_zip)

        with zipfile.ZipFile(out_zip, "r") as zout:
            names = zout.namelist()
            assert any("intro.md" in n for n in names)
            assert any("data.md" in n for n in names)


def test_batch_service_error_isolation():
    """Verify that a corrupted file does not abort other valid file conversions."""
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as out_dir:
        # Valid document
        with open(os.path.join(src_dir, "valid.md"), "w", encoding="utf-8") as f:
            f.write("# Valid Doc")

        # Fake docx that is corrupted
        with open(os.path.join(src_dir, "corrupted.docx"), "wb") as f:
            f.write(b"NOT_A_VALID_DOCX_FILE_HEADER")

        service = BatchConversionService()
        res = service.run_batch(
            source_path=src_dir,
            target_ext=".md",
            output_destination=out_dir,
            output_type="folder",
        )

        # Total is 2: 1 succeeded, 1 failed (corrupted file isolated)
        assert res.total == 2
        assert res.succeeded == 1
        assert res.failed == 1
        assert len(res.errors) == 1
        assert os.path.exists(os.path.join(out_dir, "valid.md"))


def test_batch_service_cancellation():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as out_dir:
        for i in range(10):
            with open(os.path.join(src_dir, f"doc_{i}.md"), "w", encoding="utf-8") as f:
                f.write(f"# Document {i}")

        service = BatchConversionService(max_workers=1)

        def cancel_on_prog(curr, tot, name, res):
            if curr >= 1:
                service.cancel()

        res = service.run_batch(
            source_path=src_dir,
            target_ext=".html",
            output_destination=out_dir,
            output_type="folder",
            on_progress=cancel_on_prog,
        )

        assert service.is_cancelled()
