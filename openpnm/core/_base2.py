import numpy as np
from openpnm.core import LabelMixin, ParamMixin, ParserMixin, ModelsDict
from openpnm.utils import Workspace, SettingsAttr
from copy import deepcopy
from uuid import uuid4


ws = Workspace()


__all__ = [
    'Base2',
    'Domain',
]


class BaseSettings:
    r"""
    The default settings to use on instance of Base

    Parameters
    ----------
    prefix : str
        The default prefix to use when generating a name
    name : str
        The name of the object, which will be generated if not given
    uuid : str
        A universally unique identifier for the object to keep things straight

    """
    prefix = 'base'
    name = ''
    uuid = ''


class Base2(dict):
    r"""
    This deals with the original openpnm dict read/write logic
    """

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls, *args, **kwargs)
        instance._settings = None
        instance._settings_docs = None
        return instance

    def __init__(self, project=None, network=None, settings=None, name=None):
        super().__init__()
        self.settings = SettingsAttr(BaseSettings, settings)
        if project is None:
            if network is None:
                project = ws.new_project()
            else:
                project = network.project
        if name is None:
            name = project._generate_name(self)
        project._validate_name(name)
        project.extend(self)
        self.settings['name'] = name
        self.settings.uuid = str(uuid4())

    def __repr__(self):
        module = self.__module__
        module = ".".join([x for x in module.split(".") if not x.startswith("_")])
        cname = self.__class__.__name__
        return f'<{module}.{cname} at {hex(id(self))}>'

    def __setitem__(self, key, value):
        if value is None:
            return

        element, prop = key.split('.', 1)

        # Catch parameters and divert to params attr
        # if element == 'param':
        #     self.params[key] = value
        #     return

        # Catch dictionaries and break them up
        if isinstance(value, dict):
            for k, v in value.items():
                self[key+'.'+k] = v
            return

        # Enfore correct dict naming
        if element not in ['pore', 'throat']:
            raise Exception('All keys must start with either pore, or throat')

        # Convert value to ndarray
        if not isinstance(value, np.ndarray):
            value = np.array(value, ndmin=1)

        # Skip checks for coords and conns
        if key in ['pore.coords', 'throat.conns']:
            self.update({key: value})
            return

        # Finally write data
        if self._count(element) is None:
            self.update({key: value})  # If length not defined, do it
            # Alternative
            # raise Exception('pore.coords and throat.conns must be defined first')
        elif value.shape[0] == 1:  # If value is scalar
            value = np.ones((self._count(element), ), dtype=value.dtype)*value
            self.update({key: value})
        elif np.shape(value)[0] == self._count(element):
            self.update({key: value})
        else:
            raise Exception('Provided array is wrong length for ' + key)

    def __getitem__(self, key):
        # If the key is a just a numerical value, the kick it directly back.
        # This allows one to do either value='pore.blah' or value=1.0 in
        # pore-scale models
        if not isinstance(key, str):
            return key

        element, prop = key.split('.', 1)
        try:
            return super().__getitem__(key)
        except KeyError:
            if key.split('.')[1] == self.name:
                self['pore.'+self.name] = np.ones(self.Np, dtype=bool)
                self['throat.'+self.name] = np.ones(self.Nt, dtype=bool)
                return self[key]
            else:
                vals = {}
                keys = self.keys()
                vals.update({k: self.get(k) for k in keys if k.startswith(key + '.')})
                if len(vals) > 0:
                    return vals
                else:
                    raise KeyError(key)

    def __delitem__(self, key):
        try:
            super().__delitem__(key)
        except KeyError:
            d = self[key]  # if key is a nested dict, get all values
            for item in d.keys():
                super().__delitem__(item)

    def _set_name(self, name, validate=True):
        old_name = self.settings['name']
        if name == old_name:
            return
        if name is None:
            name = self.project._generate_name(self)
        if validate:
            self.project._validate_name(name)
        self.settings['name'] = name

    def _get_name(self):
        """String representing the name of the object"""
        try:
            return self.settings['name']
        except AttributeError:
            return None

    name = property(_get_name, _set_name)

    def _get_project(self):
        """A shortcut to get a handle to the associated project."""
        for proj in ws.values():
            if self in proj:
                return proj

    project = property(fget=_get_project)

    def _set_settings(self, settings):
        self._settings = deepcopy(settings)
        if (self._settings_docs is None) and (settings.__doc__ is not None):
            self._settings_docs = settings.__doc__

    def _get_settings(self):
        """Dictionary containing object settings."""
        if self._settings is None:
            self._settings = SettingsAttr()
        if self._settings_docs is not None:
            self._settings.__dict__['__doc__'] = self._settings_docs
        return self._settings

    def _del_settings(self):
        self._settings = None

    settings = property(fget=_get_settings, fset=_set_settings, fdel=_del_settings)

    @property
    def network(self):
        r"""
        A shortcut to get a handle to the associated network.
        There can only be one so this works.
        """
        return self.project.network

    @property
    def _domain(self):
        return self

    def _count(self, element):
        for k, v in self.items():
            if k.startswith(element):
                return v.shape[0]
        # Alternative
        # if element == 'pore':
        #     try:
        #         return self['pore.coords'].shape[0]
        #     except KeyError:
        #         return None
        # elif element == 'throat':
        #     try:
        #         return self['throat.conns'].shape[0]
        #     except KeyError:
        #         return None

    @property
    def Nt(self):
        return self._count('throat')

    @property
    def Np(self):
        return self._count('pore')

    @property
    def Ts(self):
        return np.arange(self._count('throat'))

    @property
    def Ps(self):
        return np.arange(self._count('pore'))

    def to_mask(self, pores=None, throats=None):
        if pores is not None:
            indices = np.array(pores, ndmin=1)
            N = self.Np
        elif throats is not None:
            indices = np.array(throats, ndmin=1)
            N = self.Nt
        else:
            raise Exception('Must specify either pores or throats')
        mask = np.zeros((N, ), dtype=bool)
        mask[indices] = True
        return mask

    def to_indices(self, mask):
        mask = np.array(mask, dtype=bool)
        return np.where(mask)[0]

    def props(self, element=['pore', 'throat']):
        if isinstance(element, str):
            element = [element]
        props = []
        for k, v in self.items():
            if v.dtype != bool:
                if k.split('.', 1)[0] in element:
                    props.append(k)
        return props

    def interpolate_data(self, propname, mode='mean'):
        from openpnm.models.misc import from_neighbor_throats, from_neighbor_pores
        if propname.startswith('throat'):
            values = from_neighbor_throats(target=self, prop=propname, mode=mode)
        elif propname.startswith('pore'):
            values = from_neighbor_pores(target=self, prop=propname, mode=mode)
        return values

    def get_conduit_data(self, poreprop, throatprop=None, mode='mean'):
        # Deal with various args
        if not poreprop.startswith('pore'):
            poreprop = 'pore.' + poreprop
        if throatprop is None:
            throatprop = 'throat.' + poreprop.split('.', 1)[1]
        if not throatprop.startswith('throat'):
            throatprop = 'throat.' + throatprop
        # Generate array
        conns = self.network.conns
        try:
            T = self[throatprop]
            try:
                P1, P2 = self[poreprop][conns.T]
            except KeyError:
                P = self.interpolate_data(propname=throatprop, mode=mode)
                P1, P2 = P[conns.T]
        except KeyError:
            P1, P2 = self[poreprop][conns.T]
            T = self.interpolate_data(propname=poreprop, mode=mode)
        return np.vstack((P1, T, P2)).T

    def __str__(self):
        module = self.__module__
        module = ".".join([x for x in module.split(".") if not x.startswith("_")])
        cname = self.__class__.__name__
        horizontal_rule = '―' * 78
        lines = [horizontal_rule]
        lines.append(f"{module}.{cname} : {self.name}")
        lines.append(horizontal_rule)
        lines.append("{0:<5s} {1:<45s} {2:<10s}".format('#',
                                                        'Properties',
                                                        'Valid Values'))
        fmt = "{0:<5d} {1:<45s} {2:>5d} / {3:<5d}"
        lines.append(horizontal_rule)
        props = self.props()
        props.sort()
        for i, item in enumerate(props):
            prop = item
            required = self._count(item.split('.')[0])
            if len(prop) > 35:  # Trim overly long prop names
                prop = prop[0:32] + '...'
            if self[item].dtype == object:  # Print objects differently
                invalid = [i for i in self[item] if i is None]
                defined = np.size(self[item]) - len(invalid)
                lines.append(fmt.format(i + 1, prop, defined, required))
            elif '._' not in prop:
                a = np.isnan(self[item])
                defined = np.shape(self[item])[0] \
                    - a.sum(axis=0, keepdims=(a.ndim-1) == 0)[0]
                lines.append(fmt.format(i + 1, prop, defined, required))
        lines.append(horizontal_rule)
        return '\n'.join(lines)


class ModelMixin2:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.models = ModelsDict()

    def add_model(self, propname, model, domain=None, regen_mode='normal', **kwargs):
        if domain is None:
            domain = ''
        else:
            domain = '@'+domain.split('.')[-1]
        self.models[propname+domain] = {}
        self.models[propname+domain]['model'] = model
        self.models[propname+domain]['regen_mode'] = regen_mode
        for item in kwargs:
            self.models[propname+domain][item] = kwargs[item]

    def regenerate_models(self):
        for item in self.models.keys():
            self.run_model(item)

    def run_model(self, propname, domain=None):
        if domain is None:
            if '@' in propname:
                for item in self.models.keys():
                    if item.startswith(propname):
                        domain = item.split('@')[-1]
                        self.run_model(propname=propname, domain=domain)
            else:
                element, prop = propname.split('.', 1)
                model = self.models[propname]['model']
                # Collect kwargs
                kwargs = {}
                for item in self.models[propname].keys():
                    if item not in ['model', 'regen_mode']:
                        kwargs[item] = self.models[propname][item]
                vals = model(target=self, **kwargs)
                self[propname] = vals
        else:
            domain = domain.split('.')[-1]
            element, prop = propname.split('@')[0].split('.', 1)
            propname = element+'.'+prop
            model = self.models[propname+'@'+domain]['model']
            # Collect kwargs
            kwargs = {}
            for item in self.models[propname+'@'+domain].keys():
                if item not in ['model', 'regen_mode']:
                    kwargs[item] = self.models[propname+'@'+domain][item]
            vals = model(target=self, domain=element+'.'+domain, **kwargs)
            if propname not in self.keys():
                self[propname] = np.nan*np.ones([self.Np, *vals.shape[1:]])
            self[propname][self[element+'.'+domain]] = vals


class Domain(ParserMixin, ParamMixin, LabelMixin, ModelMixin2, Base2):
    r"""
    This adds the new domain-based read/write logic
    """

    def __getitem__(self, key):
        if '@' in key:
            element, prop = key.split('@')[0].split('.', 1)
            domain = key.split('@')[1].split('.')[-1]
            locs = super().__getitem__(element+'.'+domain)
            vals = super().__getitem__(element+'.'+prop)
            return vals[locs]
        else:
            return super().__getitem__(key)

    def __setitem__(self, key, value):
        if '@' in key:
            element, prop = key.split('@')[0].split('.', 1)
            domain = key.split('@')[1].split('.')[-1]
            locs = super().__getitem__(element+'.'+domain)
            try:
                vals = self[element+'.'+prop]
                vals[locs] = value
                self[element+'.'+prop] = vals
            except KeyError:
                value = np.array(value)
                temp = np.zeros([self.Np, *value.shape[1:]], dtype=bool)
                if value.dtype != bool:
                    temp = temp*np.nan
                super().__setitem__(element+'.'+prop, temp)
                self[element+'.'+prop][locs] = value
        else:
            super().__setitem__(key, value)


def random_seed(target, domain, seed=None, lim=[0, 1]):
    inds = target[domain]
    np.random.seed(seed)
    seeds = np.random.rand(inds.sum())*(lim[1]-lim[0]) + lim[0]
    return seeds


def factor(target, prop, f=1):
    vals = target[prop]*f
    return vals


if __name__ == '__main__':

    # %%
    import openpnm as op
    import pytest
    pn = op.network.Cubic(shape=[3, 3, 1])
    g = Domain()
    g.name = 'bob'
    g['pore.coords'] = pn.pop('pore.coords')
    g['throat.conns'] = pn.pop('throat.conns')
    for k, v in pn.items():
        g[k] = v

    g.add_model(propname='pore.seed',
                model=random_seed,
                domain='pore.left',
                lim=[0.2, 0.4])
    g.add_model(propname='pore.seed',
                model=random_seed,
                domain='right',
                lim=[0.7, 0.99])
    g.add_model(propname='pore.seedx',
                model=factor,
                prop='pore.seed',
                f=10)

    # %% Run some basic tests
    # Use official args
    g.run_model('pore.seed', domain='pore.left')
    assert np.sum(~np.isnan(g['pore.seed'])) == g['pore.left'].sum()
    # Use partial syntax
    g.run_model('pore.seed', domain='left')
    assert np.sum(~np.isnan(g['pore.seed'])) == g['pore.left'].sum()
    # Use lazy syntax
    g.run_model('pore.seed@right')
    assert np.sum(np.isnan(g['pore.seed'])) == 3
    # Full domain model
    g.run_model('pore.seedx')
    assert 'pore.seedx' in g.keys()
    x = g['pore.seedx']
    assert x[~np.isnan(x)].min() > 2
    # Fetch data with lazy syntax
    assert g['pore.seed@left'].shape[0] == 3
    # Write data with lazy syntax, ensuring scalar to array conversion
    g['pore.seed@right'] = np.nan
    assert np.sum(~np.isnan(g['pore.seed'])) == g['pore.left'].sum()
    # Write array directly
    g['pore.seed@right'] = np.ones(3)*3
    assert np.sum(np.isnan(g['pore.seed'])) == 3
    # Use labels that were not used by models
    assert g['pore.seed@front'].shape[0] == 3
    # Write a dict
    g['pore.dict'] = {'pore.item1': 1, 'pore.item2': 1}
    assert g['pore.item1'].sum() == 9
    assert g['pore.item2'].sum() == 9
    # A dict with domains
    g['pore.dict'] = {'pore.item1@left': 2, 'pore.item2@right': 2}
    assert g['pore.item1'].sum() == 12
    assert g['pore.item2'].sum() == 12
    g['pore.nested.name1'] = 10
    g['pore.nested.name2'] = 20
    assert isinstance(g['pore.nested'], dict)
    # assert len(g['pore.nested']) == 2
    with pytest.raises(KeyError):
        g['pore.nested.fail']
    del g['pore.nested.name1']
    assert 'pore.nested.name1' not in g.keys()
    del g['pore.nested']
    assert 'pore.nested.name2' not in g.keys()





















