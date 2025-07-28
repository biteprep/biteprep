# quiz/templatetags/custom_filters.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    # This filter allows you to access a dictionary item with a variable key in a template
    if isinstance(dictionary, dict):
        return dictionary.get(str(key))
    return None

@register.filter(name='replace')
def replace(value, arg):
    """
    Replacing filter
    Use: {{ "aaa"|replace:"a|b" }}
    """
    if len(arg.split('|')) != 2:
        return value

    what, to = arg.split('|')
    return value.replace(what, to)

@register.simple_tag(takes_context=False)
def set(value):
  return value