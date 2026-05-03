from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get a value from a dict in templates: {{ mydict|get_item:key }}"""
    return dictionary.get(key)


@register.filter
def multiply(value, arg):
    """Multiply: {{ value|multiply:2 }}"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """Divide: {{ value|divide:12 }}"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def subtract(value, arg):
    """Subtract: {{ value|subtract:arg }}"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def absolute(value):
    """Absolute value: {{ value|absolute }}"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return 0