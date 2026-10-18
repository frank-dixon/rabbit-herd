"""Photo storage that never deletes a demo-baseline file.

Every "See a demo herd" copy points at the baseline herd's photo files rather
than duplicating them (accounts.demo), so a demo visitor deleting or replacing
a photo must not remove the shared file. Deletes of names under the baseline
owner's folders are skipped; everything else behaves as the normal storage."""

from django.core.files.storage import FileSystemStorage


def is_protected(name):
    try:
        from accounts.demo import protected_prefixes

        return bool(name) and str(name).startswith(protected_prefixes())
    except Exception:  # no database yet (collectstatic, early start-up): nothing to protect
        return False


class ProtectedDeleteMixin:
    def delete(self, name):
        if is_protected(name):
            return
        return super().delete(name)


class PhotoFileSystemStorage(ProtectedDeleteMixin, FileSystemStorage):
    pass


def _s3():
    from storages.backends.s3 import S3Storage

    class PhotoS3Storage(ProtectedDeleteMixin, S3Storage):
        pass

    return PhotoS3Storage


def __getattr__(name):
    # Imported lazily so the local filesystem setup needs no S3 libraries.
    if name == "PhotoS3Storage":
        cls = _s3()
        globals()[name] = cls
        return cls
    raise AttributeError(name)
