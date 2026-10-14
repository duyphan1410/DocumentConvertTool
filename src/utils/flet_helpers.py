def safe_page(*controls):
    """Return the first mounted page among controls; flet >= 0.80 raises RuntimeError if unmounted."""
    for ctrl in controls:
        if ctrl is None:
            continue
        try:
            page = ctrl.page
        except (RuntimeError, AttributeError):
            continue
        if page:
            return page
    return None