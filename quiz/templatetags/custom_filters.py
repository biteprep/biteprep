# quiz/templatetags/custom_filters.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Allows you to get an item from a dictionary using a variable as the key.
    Usage: {{ my_dictionary|get_item:my_variable_key }}
    """
    if isinstance(dictionary, dict):
        # We need to handle both integer and string keys
        return dictionary.get(str(key))
    return None