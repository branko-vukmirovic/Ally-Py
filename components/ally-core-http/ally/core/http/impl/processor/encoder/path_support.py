'''
Created on Mar 15, 2013

@package: ally core http
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the path support.
'''

from ally.api.operator.container import Model
from ally.api.operator.type import TypeModel, TypeModelProperty
from ally.api.type import Iter
from ally.container.ioc import injected
from ally.core.spec.resources import Path
from ally.core.spec.transform.encoder import IEncoder
from ally.design.cache import CacheWeak
from ally.design.processor.attribute import requires, defines, definesIf
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessorProceed
from ally.support.core.util_resources import findGetModel, findGetAllAccessible, \
    pathLongName
from collections import OrderedDict

# --------------------------------------------------------------------

class Create(Context):
    '''
    The create encoder context.
    '''
    # ---------------------------------------------------------------- Required
    objType = requires(object)
    
class Support(Context):
    '''
    The support context.
    '''
    # ---------------------------------------------------------------- Defined
    pathModel = defines(Path, doc='''
    @rtype: Path
    The path of the encoded model.
    ''')
    pathsProperties = defines(dict, doc='''
    @rtype: dictionary{TypeModelProperty: Path}
    The paths of the model properties, this paths need to be updated by the encoder,
    this paths are linked with the model path.
    ''')
    pathsAccesible = defines(dict, doc='''
    @rtype: dictionary{string: Path}
    The accessible paths, this paths are linked with the model path.
    ''')
    updatePaths = defines(dict, doc='''
    @rtype: dictionary{Type: Path}
    The paths to be updated based on type object.
    ''')
    hideProperties = definesIf(bool, doc='''
    @rtype: boolean
    Flag indicating that the properties should be rendered or not.
    ''')
    # ---------------------------------------------------------------- Required
    path = requires(Path)
    
class CreateItem(Create):
    '''
    The create item encoder context.
    '''
    # ---------------------------------------------------------------- Required
    encoder = requires(IEncoder)

class SupportItem(Context):
    '''
    The encoder item support context.
    '''
    # ---------------------------------------------------------------- Required
    updatePaths = requires(dict)
    
# --------------------------------------------------------------------

@injected
class PathSupport(HandlerProcessorProceed):
    '''
    Implementation for a handler that provides the path support.
    '''
        
    def process(self, create:Create, support:Support, **keyargs):
        '''
        @see: HandlerProcessorProceed.process
        
        Populates the path support data.
        '''
        assert isinstance(create, Create), 'Invalid create %s' % create
        assert isinstance(support, Support), 'Invalid support %s' % support
        
        objType = create.objType
        if isinstance(objType, Iter):
            assert isinstance(objType, Iter)
            objType = objType.itemType
            inCollection = True
        else: inCollection = False
        
        if isinstance(objType, TypeModel):
            modelType = objType
            propType = None
        elif isinstance(objType, TypeModelProperty):
            assert isinstance(objType, TypeModelProperty)
            modelType = objType.parent
            propType = objType
        else: return  # Cannot use the object type, moving along
        
        assert isinstance(support.path, Path), 'Invalid path %s' % support.path
        
        if support.updatePaths is None: support.updatePaths = {}
        if support.pathsProperties is None: support.pathsProperties = {}
        if support.pathsAccesible is None: support.pathsAccesible = OrderedDict()
        
        if inCollection: pathModel = findGetModel(support.path, modelType)
        else: pathModel = support.path
        if pathModel is None: return  # No model path available
        support.pathModel = pathModel
        
        if propType:
            assert isinstance(propType, TypeModelProperty)
            if propType.isId():
                support.updatePaths[propType] = pathModel
                support.hideProperties = True
            else: support.pathModel = None
            return  # If not a model no other paths are required.
        
        if inCollection:
            support.updatePaths[modelType] = pathModel
            support.hideProperties = True
            # TODO: Gabriel: This is a temporary fix to get the same rendering as before until we refactor the plugins
            # to return only ids.
            return
        
        assert isinstance(modelType, TypeModel)
        assert isinstance(modelType.container, Model)
        for valueType in modelType.container.properties.values():
            if isinstance(valueType, TypeModel):
                assert isinstance(valueType, TypeModel)
                pathProp = findGetModel(pathModel, valueType)
                if pathProp: support.pathsProperties[valueType.propertyTypeId()] = pathProp
                
        # Make sure when placing the accessible paths that there isn't already an accessible path
        # that already returns the inherited model see the example for MetaData and ImageData in relation
        # with MetaInfo and ImageInfo
        for path in findGetAllAccessible(pathModel):
            pathName = pathLongName(path)
            if pathName not in support.pathsAccesible: support.pathsAccesible[pathName] = path
        # These paths will get updated in the encode model when the data model path is updated
        # because they are extended from the base path.
        for parentType in modelType.parents():
            parentPath = findGetModel(pathModel, parentType)
            if parentPath:
                for path in findGetAllAccessible(parentPath):
                    pathName = pathLongName(path)
                    if pathName not in support.pathsAccesible:
                        if parentType not in support.updatePaths: support.updatePaths[parentType] = parentPath
                        support.pathsAccesible[pathName] = path

@injected
class PathUpdaterSupportEncode(HandlerProcessorProceed):
    '''
    Implementation for a handler that provides the models paths update when in a collection.
    '''
    
    def __init__(self):
        super().__init__(support=SupportItem)
        
        self._cache = CacheWeak()
        
    def process(self, create:CreateItem, **keyargs):
        '''
        @see: HandlerProcessorProceed.process
        
        Create the update model path encoder.
        '''
        assert isinstance(create, CreateItem), 'Invalid create %s' % create
        
        if create.encoder is None: return 
        # There is no encoder to provide path update for.
        if not isinstance(create.objType, (TypeModel, TypeModelProperty)): return 
        # The type is not for a path updater, nothing to do, just move along
        
        cache = self._cache.key(create.encoder)
        if not cache.has: cache.value = EncoderPathUpdater(create.encoder)
        
        create.encoder = cache.value
        
# --------------------------------------------------------------------

class EncoderPathUpdater(IEncoder):
    '''
    Implementation for a @see: IEncoder that updates the path before encoding .
    '''
    
    def __init__(self, encoder):
        '''
        Construct the path updater.
        '''
        assert isinstance(encoder, IEncoder), 'Invalid property encoder %s' % encoder
        
        self.encoder = encoder
        
    def render(self, obj, render, support):
        '''
        @see: IEncoder.render
        '''
        assert isinstance(support, SupportItem), 'Invalid support %s' % support
        if support.updatePaths:
            assert isinstance(support.updatePaths, dict), 'Invalid update paths %s' % support.updatePaths
            for objType, path in support.updatePaths.items():
                assert isinstance(path, Path)
                path.update(obj, objType)
        
        self.encoder.render(obj, render, support)
