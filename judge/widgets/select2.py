# -*- coding: utf-8 -*-
"""
Select2 Widgets based on https://github.com/applegrew/django-select2.

These components are responsible for rendering
the necessary HTML data markups. Since this whole
package is to render choices using Select2 JavaScript
library, hence these components are meant to be used
with choice fields.

Widgets are generally of two types:

    1. **Light** --
    They are not meant to be used when there
    are too many options, say, in thousands.
    This is because all those options would
    have to be pre-rendered onto the page
    and JavaScript would be used to search
    through them. Said that, they are also one
    the most easiest to use. They are a
    drop-in-replacement for Django's default
    select widgets.

    2. **Heavy** --
    They are suited for scenarios when the number of options
    are large and need complex queries (from maybe different
    sources) to get the options.
    This dynamic fetching of options undoubtedly requires
    Ajax communication with the server. Django-Select2 includes
    a helper JS file which is included automatically,
    so you need not worry about writing any Ajax related JS code.
    Although on the server side you do need to create a view
    specifically to respond to the queries.

Heavy widgets have the word 'Heavy' in their name.
Light widgets are normally named, i.e. there is no
'Light' word in their names.

"""
from __future__ import absolute_import, unicode_literals

from copy import copy
from itertools import chain

from django import forms
from django.conf import settings
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core import signing
from django.core.urlresolvers import reverse_lazy
from django.forms.models import ModelChoiceIterator
from django.utils.encoding import force_text


DEFAULT_SELECT2_JS = '//cdnjs.cloudflare.com/ajax/libs/select2/4.0.3/js/select2.min.js'
DEFAULT_SELECT2_CSS = '//cdnjs.cloudflare.com/ajax/libs/select2/4.0.3/css/select2.min.css'

__all__ = ['Select2Widget', 'Select2MultipleWidget', 'Select2TagWidget',
           'HeavySelect2Widget', 'HeavySelect2MultipleWidget', 'HeavySelect2TagWidget']


class Select2Mixin(object):
    """
    The base mixin of all Select2 widgets.

    This mixin is responsible for rendering the necessary
    data attributes for select2 as well as adding the static
    form media.
    """

    def build_attrs(self, extra_attrs=None, **kwargs):
        """Add select2 data attributes."""
        attrs = super(Select2Mixin, self).build_attrs(extra_attrs=extra_attrs, **kwargs)
        if self.is_required:
            attrs.setdefault('data-allow-clear', 'false')
        else:
            attrs.setdefault('data-allow-clear', 'true')
            attrs.setdefault('data-placeholder', '')

        attrs.setdefault('data-minimum-input-length', 0)
        if 'class' in attrs:
            attrs['class'] += ' django-select2'
        else:
            attrs['class'] = 'django-select2'
        return attrs

    def render_options(self, choices, selected_choices):
        """Render options including an empty one, if the field is not required."""
        output = '<option></option>' if not self.is_required else ''
        output += super(Select2Mixin, self).render_options(choices, selected_choices)
        return output

    def _get_media(self):
        """
        Construct Media as a dynamic property.

        .. Note:: For more information visit
            https://docs.djangoproject.com/en/1.8/topics/forms/media/#media-as-a-dynamic-property
        """
        return forms.Media(
            js=(getattr(settings, 'SELECT2_JS_URL', DEFAULT_SELECT2_JS),
                static('django_select2.js')),
            css={'screen': (getattr(settings, 'SELECT2_CSS_URL', DEFAULT_SELECT2_CSS),)}
        )

    media = property(_get_media)


class Select2TagMixin(object):
    """Mixin to add select2 tag functionality."""

    def build_attrs(self, extra_attrs=None, **kwargs):
        """Add select2's tag attributes."""
        self.attrs.setdefault('data-minimum-input-length', 1)
        self.attrs.setdefault('data-tags', 'true')
        self.attrs.setdefault('data-token-separators', [",", " "])
        return super(Select2TagMixin, self).build_attrs(extra_attrs, **kwargs)


class Select2Widget(Select2Mixin, forms.Select):
    """
    Select2 drop in widget.

    Example usage::

        class MyModelForm(forms.ModelForm):
            class Meta:
                model = MyModel
                fields = ('my_field', )
                widgets = {
                    'my_field': Select2Widget
                }

    or::

        class MyForm(forms.Form):
            my_choice = forms.ChoiceField(widget=Select2Widget)

    """

    pass


class Select2MultipleWidget(Select2Mixin, forms.SelectMultiple):
    """
    Select2 drop in widget for multiple select.

    Works just like :class:`.Select2Widget` but for multi select.
    """

    pass


class Select2TagWidget(Select2TagMixin, Select2Mixin, forms.SelectMultiple):
    """
    Select2 drop in widget for for tagging.

    Example for :class:`.django.contrib.postgres.fields.ArrayField`::

        class MyWidget(Select2TagWidget):

            def value_from_datadict(self, data, files, name):
                values = super(MyWidget, self).value_from_datadict(data, files, name):
                return ",".join(values)

    """

    pass


class HeavySelect2Mixin(Select2Mixin):
    """Mixin that adds select2's ajax options."""

    def __init__(self, **kwargs):
        """
        Return HeavySelect2Mixin.

        :param data_view: url pattern name
        :type data_view: str
        :param data_url: url
        :type data_url: str
        :return:
        """
        self.data_view = kwargs.pop('data_view', None)
        self.data_url = kwargs.pop('data_url', None)
        if not (self.data_view or self.data_url):
            raise ValueError('You must ether specify "data_view" or "data_url".')
        self.userGetValTextFuncName = kwargs.pop('userGetValTextFuncName', 'null')
        super(HeavySelect2Mixin, self).__init__(**kwargs)

    def get_url(self):
        """Return url from instance or by reversing :attr:`.data_view`."""
        if self.data_url:
            return self.data_url
        return reverse_lazy(self.data_view)

    def build_attrs(self, extra_attrs=None, **kwargs):
        """Set select2's ajax attributes."""
        attrs = super(HeavySelect2Mixin, self).build_attrs(extra_attrs=extra_attrs, **kwargs)

        # encrypt instance Id
        self.widget_id = signing.dumps(id(self))

        attrs['data-field_id'] = self.widget_id
        attrs.setdefault('data-ajax--url', self.get_url())
        attrs.setdefault('data-ajax--cache', "true")
        attrs.setdefault('data-ajax--type', "GET")
        attrs.setdefault('data-minimum-input-length', 2)

        attrs['class'] += ' django-select2-heavy'
        return attrs

    def render_options(self, choices, selected_choices):
        """Render only selected options."""
        output = ['<option></option>' if not self.is_required else '']
        if isinstance(self.choices, ModelChoiceIterator):
            chosen = copy(self.choices)
            chosen.queryset = chosen.queryset.filter(pk__in=[int(i) for i in selected_choices
                                                             if isinstance(i, (int, long)) or i.isdigit()])
            chosen = set(chosen)
        else:
            choices = chain(self.choices, choices)
            chosen = set()

        selected_choices = {force_text(v) for v in selected_choices}
        chosen.update((k, v) for k, v in choices if force_text(k) in selected_choices)

        for option_value, option_label in chosen:
            output.append(self.render_option(selected_choices, option_value, option_label))
        return '\n'.join(output)


class HeavySelect2Widget(HeavySelect2Mixin, forms.Select):
    """
    Select2 widget with AJAX support.

    Usage example::

        class MyWidget(HeavySelectWidget):
            data_view = 'my_view_name'

    or::

        class MyForm(forms.Form):
            my_field = forms.ChoicesField(
                widget=HeavySelectWidget(
                    data_url='/url/to/json/response'
                )
            )

    """

    pass


class HeavySelect2MultipleWidget(HeavySelect2Mixin, forms.SelectMultiple):
    """Select2 multi select widget similar to :class:`.HeavySelect2Widget`."""

    pass


class HeavySelect2TagWidget(Select2TagMixin, HeavySelect2MultipleWidget):
    """Select2 tag widget."""

    pass
