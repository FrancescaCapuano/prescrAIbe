def context_is_in_leaflet(context, leaflet):
    """
    Check if a given context is present in the leaflet text.

    Args:
        context (str): The context to check.
        leaflet (str): The text of the leaflet.

    Returns:
        bool: True if the context is found in the leaflet, False otherwise.
    """
    return context.lower() in leaflet.lower()
