'''
Created on Mar 8, 2013

@package: ally core
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the primitive properties encoder.
'''

from ally.api.operator.type import TypeProperty
from ally.api.type import Iter
from ally.container.ioc import injected
from ally.core.spec.resources import Normalizer, Converter
from ally.core.spec.transform.encoder import DO_RENDER
from ally.core.spec.transform.render import IRender
from ally.design.processor.attribute import requires
from ally.design.processor.context import Context
from ally.design.processor.execution import Chain
from ally.design.processor.handler import HandlerProcessor
from collections import Iterable

# --------------------------------------------------------------------

class Response(Context):
    '''
    The encoded response context.
    '''
    # ---------------------------------------------------------------- Required
    action = requires(int)
    normalizer = requires(Normalizer)
    converter = requires(Converter)

class Encode(Context):
    '''
    The encode context.
    '''
    # ---------------------------------------------------------------- Required
    name = requires(str)
    obj = requires(object)
    objType = requires(object)
    render = requires(IRender)
    
# --------------------------------------------------------------------

@injected
class PropertyEncode(HandlerProcessor):
    '''
    Implementation for a handler that provides the primitive properties values encoding.
    '''
    
    nameValue = 'Value'
    # The name to use for rendering the values in a collection property.
    
    def __init__(self):
        assert isinstance(self.nameValue, str), 'Invalid name value list %s' % self.nameValue
        super().__init__()
        
    def process(self, chain, response:Response, encode:Encode, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Encode the property.
        '''
        assert isinstance(chain, Chain), 'Invalid chain %s' % chain
        assert isinstance(response, Response), 'Invalid response %s' % response
        assert isinstance(encode, Encode), 'Invalid encode %s' % encode
        
        if not response.action & DO_RENDER:
            # If no rendering is required we just proceed, maybe other processors might do something
            chain.proceed()
            return
        
        if not isinstance(encode.objType, TypeProperty):  # The type is not for a property, nothing to do, just move along
            chain.proceed()
            return
        valueType = encode.objType.type
        
        assert encode.obj is not None, 'An object is required for rendering'
        assert isinstance(encode.name, str), 'Invalid property name %s' % encode.name
        assert isinstance(encode.render, IRender), 'Invalid render %s' % encode.render
        assert isinstance(response.normalizer, Normalizer), 'Invalid normalizer %s' % response.normalizer
        assert isinstance(response.converter, Converter), 'Invalid converter %s' % response.converter

        if isinstance(valueType, Iter):
            assert isinstance(valueType, Iter)
            assert isinstance(encode.obj, Iterable), 'Invalid encode object %s' % encode.obj
            valueType = valueType.itemType
            
            encode.render.collectionStart(encode.name)
            nameValue = response.normalizer.normalize(self.nameValue)
            for value in encode.obj: encode.render.value(nameValue, response.converter.asString(value, valueType))
            encode.render.collectionEnd()
            return
        
        encode.render.value(response.normalizer.normalize(encode.name), response.converter.asString(encode.obj, valueType))
