# We need to put these in a separate module so they're easy to import
# on a test-by-test basis so that we can skip django-requiring tests
# if django isn't installed.
from uuid import UUID


from elasticutils.contrib.django import MappingType, Indexable


_model_cache = []


def reset_model_cache():
    del _model_cache[0:]


class Meta(object):
    def __init__(self, db_table):
        self.db_table = db_table


class SearchQuerySet(object):
    # Yes. This is kind of crazy, but ... whatever.
    def __init__(self, model):
        self.model = model
        self.id_field = model.id_field
        self.steps = []

    def get(self, pk=None, uuid=None):
        if pk:
            pk = int(pk)
            return [m for m in _model_cache if m.id == pk][0]
        if uuid:
            uuid = UUID(uuid)
            return [m for m in _model_cache if m.uuid == uuid][0]
        return []

    def filter(self, id__in=None, uuid__in=None):
        self.steps.append(('filter', id__in or uuid__in))
        return self

    def order_by(self, *fields):
        self.steps.append(('order_by', fields))
        return self

    def values_list(self, *args, **kwargs):
        self.steps.append(('values_list', args, kwargs.pop('flat', False)))
        return self

    def __iter__(self):
        order_by = None
        values_list = None
        objs = _model_cache

        for mem in self.steps:
            if mem[0] == 'filter':
                objs = [obj for obj in objs
                        if getattr(obj, self.id_field) in mem[1]]
            elif mem[0] == 'order_by':
                order_by_field = mem[1][0]
            elif mem[0] == 'values_list':
                values_list = (mem[1], mem[2])

        if order_by:
            objs.sort(key=getattr(obj, order_by_field))

        if values_list:
            # Note: Hard-coded to just id and flat
            objs = [getattr(obj, self.id_field) for obj in objs]
        return iter(objs)


class Manager(object):
    def get_query_set(self):
        return SearchQuerySet(self)

    def get(self, pk=None, uuid=None):
        return self.get_query_set().get(pk=pk, uuid=uuid)

    def filter(self, *args, **kwargs):
        return self.get_query_set().filter(*args, **kwargs)

    def order_by(self, *args, **kwargs):
        return self.get_query_set().order_by(*args, **kwargs)

    def values_list(self, *args, **kwargs):
        return self.get_query_set().values_list(*args, **kwargs)


class FakeModel(object):
    _meta = Meta('fake')
    objects = Manager()

    def __init__(self, **kw):
        self.objects.id_field = kw.pop('id_field', 'id')
        self._doc = kw
        for key in kw:
            setattr(self, key, kw[key])
        _model_cache.append(self)


class FakeDjangoMappingType(MappingType, Indexable):
    @classmethod
    def get_model(cls):
        return FakeModel

    @classmethod
    def extract_document(cls, obj_id, obj=None):
        if obj is None:
            raise ValueError('I\'m a dumb mock object and I have no idea '
                             'what to do with these args.')

        return obj._doc

class FakeDjangoWithUuidMappingType(FakeDjangoMappingType):
    id_field = 'uuid'

    @classmethod
    def extract_document(cls, obj_id, obj=None):
        doc = super(FakeDjangoWithUuidMappingType, cls)\
            .extract_document(obj_id, obj=obj)
        return {k:str(v) for k,v in doc.iteritems()}
