'''
Created on Feb 28, 2013

@package: support acl
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Processor that creates alternate Gateway objects for resources that are not allowed. The purpose of this is to facilitate
the client side implementation since they can use the same resources but the gateway will automatically provide a filtered
resource that is allowed by permissions.
'''

from acl.right_sevice import Alternate
from ally.api.operator.type import TypeModel
from ally.api.type import typeFor
from ally.container import wire
from ally.container.ioc import injected
from ally.container.support import setup
from ally.core.impl.invoker import InvokerCall
from ally.core.spec.resources import Node, Path, INodeChildListener, \
    INodeInvokerListener, Invoker
from ally.design.processor.attribute import defines, requires
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessorProceed, Handler
from ally.support.core.util_resources import propertyTypesOf, iterateNodes, \
    METHOD_NODE_ATTRIBUTE, invokerCallOf
from collections import Iterable, deque
import logging

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class PermissionResource(Context):
    '''
    The permission context.
    '''
    # ---------------------------------------------------------------- Required
    method = requires(int)
    path = requires(Path)
    invoker = requires(Invoker)
    filters = requires(list)
    values = requires(dict)
    
class Solicitation(Context):
    '''
    The solicitation context.
    '''
    # ---------------------------------------------------------------- Required
    permissions = requires(Iterable)

class Reply(Context):
    '''
    The reply context.
    '''
    # ---------------------------------------------------------------- Defined
    gateways = defines(Iterable, doc='''
    @rtype: Iterable(Gateway)
    The alternate generated gateways.
    ''')

# --------------------------------------------------------------------

@injected
@setup(Handler, name='gatewaysAlternateForPermissions')
class GatewaysAlternateForPermissions(HandlerProcessorProceed, INodeChildListener, INodeInvokerListener):
    '''
    Provides the handler that creates alternate gateways based on resource permissions.
    '''
    
    resourcesRoot = Node; wire.entity('resourcesRoot')
    # The root node to find the resources that can have alternate gateways.
    alternate = Alternate; wire.entity('alternate')
    # The alternate to use.

    def __init__(self):
        assert isinstance(self.resourcesRoot, Node), 'Invalid root node %s' % self.resourcesRoot
        assert isinstance(self.alternate, Alternate), 'Invalid alternate repository %s' % self.alternate
        super().__init__()
        
        self._alternates = None
        self.resourcesRoot.addStructureListener(self)
    
    def process(self, Permission:PermissionResource, solicitation:Solicitation, reply:Reply, **keyargs):
        '''
        @see: HandlerProcessorProceed.process
        
        Construct the alternate gateways for permissions.
        '''
        assert issubclass(Permission, PermissionResource), 'Invalid permission class %s' % Permission
        assert isinstance(solicitation, Solicitation), 'Invalid solicitation %s' % solicitation
        assert isinstance(reply, Reply), 'Invalid reply %s' % reply
        assert isinstance(solicitation.permissions, Iterable), 'Invalid permissions %s' % solicitation.permissions
        
        if not isinstance(solicitation.permissions, (tuple, list, deque)):
            permissions = list(solicitation.permissions)
            solicitation.permissions = permissions
        
        for permission in solicitation.permissions:
            assert isinstance(permission, PermissionResource), 'Invalid permission %s' % permission
            if PermissionResource.values not in permission: continue  # No values to work with
            
            # The alternates need to be manually configured either call to call or service to service
            # they will be handled by the resource node associate
            # create an alternate model(s) whith which you can configure this
            # refactor the structs in node associate so they will not use Bean
            # TODO: remove
            print('=' * 100)
            for key, alternates in self.alternates().items():
                for node, invoker, required in alternates:
                    assert isinstance(required, set)
                    if required.issubset(permission.values):
                        print(key[1])
                        print('\t', ', '.join(str(typ) for typ in required), ':', invoker)
                    

    # ----------------------------------------------------------------
    
    def onChildAdded(self, node, child):
        '''
        @see: INodeChildListener.onChildAdded
        '''
        self._alternates = None
    
    def onInvokerChange(self, node, old, new):
        '''
        @see: INodeInvokerListener.onInvokerChange
        '''
        self._alternates = None
        
    # ----------------------------------------------------------------
    
    def alternates(self):
        '''
        Provides the alternates.
        
        @return: dictionary{tuple(Node, Invoker): list[tuple(Node, Invoker, set(TypeProperty))]}
            The alternates dictionary, as a key a tuple with the node and invoker and as a value a set of the same tuples
            with the required property types and contains the possible alternates for the key.
        '''
        if self._alternates is None:
            self._alternates = {}
            alternatesRepository = {(typeService, call): set(alternates)
                                    for typeService, call, alternates in self.alternate.iterate()}            
            # First we process the node and invoker keys
            keys = []
            for node in iterateNodes(self.resourcesRoot):
                for _method, attr in METHOD_NODE_ATTRIBUTE.items():
                    invoker = getattr(node, attr)
                    if not invoker: continue
                    
                    keys.append((node, invoker))
            
            # Then we need to find the alternates
            pathTypesByKey, modelTypesByKey = {}, {}
            for key in keys:
                node, invoker = key
                assert isinstance(node, Node), 'Invalid node %s' % node
                assert isinstance(invoker, Invoker), 'Invalid invoker %s' % invoker
                
                for keyAlt in keys:
                    nodeAlt, invokerAlt = keyAlt
                    assert isinstance(nodeAlt, Node), 'Invalid node %s' % nodeAlt
                    assert isinstance(invokerAlt, Invoker), 'Invalid invoker %s' % invokerAlt
                    
                    if node == nodeAlt: continue  # Same node, no need to process
                    if invoker != invokerAlt:
                        if invoker.method != invokerAlt.method: continue  # Not the same method, no need to process
                        if invoker.output != invokerAlt.output: continue  # Not the same return, no need to process
                     
                    modelTypes = modelTypesByKey.get(key)
                    if modelTypes is None:
                        modelTypes = [inp.type for inp in invoker.inputs if isinstance(inp.type, TypeModel)]
                        modelTypesByKey[key] = modelTypes
    
                    modelTypesAlt = modelTypesByKey.get(keyAlt)
                    if modelTypesAlt is None:
                        modelTypesAlt = [inp.type for inp in invokerAlt.inputs if isinstance(inp.type, TypeModel)]
                        modelTypesByKey[keyAlt] = modelTypesAlt
                        
                    if modelTypes != modelTypesAlt: continue  # The model types don't match, no need to process
                   
                    pathTypes = pathTypesByKey.get(key)
                    if pathTypes is None: pathTypes = pathTypesByKey[key] = propertyTypesOf(node, invoker)
                    pathTypesAlt = pathTypesByKey.get(keyAlt)
                    if pathTypesAlt is None: pathTypesAlt = pathTypesByKey[keyAlt] = propertyTypesOf(nodeAlt, invokerAlt)
                    
                    required = set(pathTypes)
                    for pathType in pathTypesAlt:
                        try: required.remove(pathType)
                        except KeyError:  # If a type is not found it means that they are not compatible
                            required.clear()
                            break  
                    if not required: continue  # There must be at least one type required
                    
                    # Now we check with the alternates repository configurations
                    if self.processWithRepository(alternatesRepository, invoker, invokerAlt):
                        alternates = self._alternates.get(key)
                        if alternates is None: alternates = self._alternates[key] = []
                        alternates.append(keyAlt + (required,))
                        assert log.debug('Added alternate on %s for %s', invoker, invokerAlt) or True
                        
            for serviceCall, alternates in alternatesRepository.items():
                if alternates:
                    alternates = ('\t%s for %s' % serviceCallAlt for serviceCallAlt in alternates)
                    service, call = serviceCall
                    log.error('Invalid alternate configuration on %s for %s with:\n%s\n', service, call, '\n'.join(alternates))
            
        return self._alternates

    def processWithRepository(self, alternatesRepository, invoker, invokerAlt):
        '''
        Process the invoker and alternate invoker against the alternates repository.
        
        @return: boolean
            True if the invoker and alternate invoker are configured in the repository.
        '''
        assert isinstance(alternatesRepository, dict), 'Invalid alternates repository %s' % alternatesRepository
        if invoker == invokerAlt: return True  # If the invoker is the same with the alternate it is valid by default
        
        invokerCall, invokerCallAlt = invokerCallOf(invoker), invokerCallOf(invokerAlt)
        if not invoker or not invokerCallAlt: return False  # If there are no invoker call then we cannot add them
        
        assert isinstance(invokerCall, InvokerCall)
        assert isinstance(invokerCallAlt, InvokerCall)
        
        alternates = alternatesRepository.get((typeFor(invokerCallAlt.implementation), invokerCallAlt.call))
        if alternates is None: return False  # There is no alternate repository configuration for the invoker
        
        try: alternates.remove((typeFor(invokerCall.implementation), invokerCall.call))
        except KeyError: return False  # Not found in the repository alternate
        
        return True
