'''
Created on Sept 04, 2013

@package: gui core
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Mihai Gociu

Provides the synchronization with the database for actions.
'''

import logging

from security.api.right import IRightService
from ally.container import wire
from ally.container.ioc import injected
from ally.container.support import setup
from ally.design.processor.attribute import requires
from ally.design.processor.context import Context
from ally.design.processor.execution import Chain
from ally.design.processor.handler import HandlerProcessor, Handler
from ally.support.util_context import listBFS
from gui.action.api.category_group import IActionGroupService
from gui.action.api.category import IActionCategoryPrototype
from gui.action.api.category_right import IActionRightService


# --------------------------------------------------------------------
log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class Repository(Context):
    '''
    The repository context.
    '''
    # ---------------------------------------------------------------- Required
    children = requires(list)
    actions = requires(list)
    
class Solicit(Context):
    '''
    The solicit context.
    '''
    # ---------------------------------------------------------------- Required
    repository = requires(Context)
    
# --------------------------------------------------------------------

@injected
class SynchronizeCategoryActionsHandler(HandlerProcessor):
    '''
    Base implementation for a processor that synchronizes the actions of the groups and rights in the configuration file with
    the database.
    '''
    
    actionCategoryService = IActionCategoryPrototype; wire.entity('actionCategoryService')
    
    def __init__(self, Repository):
        #assert isinstance(self.actionCategoryService, IActionGroupService), \
        assert isinstance(self.actionCategoryService, IActionCategoryPrototype), \
        'Invalid action category service %s' % self.actionCategoryService
        super().__init__(Repository=Repository)
        
    def synchronize(self, entityActions):
        ''' 
        Method to synchronize actions from configuration file with the database for groups and rights.
        @param entityActions: mapping entityId : list of actions
        '''
        for entity, actions in entityActions.items():
            actionsDb = set(self.actionCategoryService.getActions(entity))
            if actions:
                actionsSet = set(action.path for action in actions)
                toDelete = actionsDb.difference(actionsSet)
                toAdd = actionsSet.difference(actionsDb)
            else:
                toDelete = actionsDb
                toAdd = None
                
            if toDelete:
                for path in toDelete:
                    self.actionCategoryService.remAction(entity, path)
            
            if toAdd:
                for path in toAdd:
                    self.actionCategoryService.addAction(entity, path)
                    
# --------------------------------------------------------------------

class RepositoryGroup(Repository):
    '''
    The repository context.
    '''
    # ---------------------------------------------------------------- Required
    groupName = requires(str)

# --------------------------------------------------------------------

@injected
@setup(Handler, name='synchronizeGroupActions')
class SynchronizeGroupActionsHandler(SynchronizeCategoryActionsHandler):
    '''
    Implementation for a processor that synchronizes the actions of the groups in the configuration file with
    the database.
    '''
    
    actionCategoryService = IActionGroupService; wire.entity('actionCategoryService')
    
    def __init__(self):
        super().__init__(Repository=RepositoryGroup)
        
    def process(self, chain, solicit:Solicit, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Synchronize the actions of the groups in the configuration file with the database.
        '''
        assert isinstance(chain, Chain), 'Invalid chain %s' % chain
        assert isinstance(solicit, Solicit), 'Invalid solicit %s' % solicit
        assert isinstance(solicit.repository, RepositoryGroup), 'Invalid repository %s' % solicit.repository
        
        groups = listBFS(solicit.repository, RepositoryGroup.children, RepositoryGroup.groupName)
        #first group the actions by group name: groupName -> [actions]
        groupActions = {}
        for group in groups:
            assert isinstance(group, RepositoryGroup), 'Invalid group %s' % group
            actions = groupActions.get(group.groupName)
            if not actions: groupActions[group.groupName] = group.actions
            else: actions.extend(group.actions)
        
        self.synchronize(groupActions)
        
# --------------------------------------------------------------------

class RepositoryRight(Repository):
    '''
    The repository context.
    '''
    # ---------------------------------------------------------------- Required
    rightName = requires(str)

# --------------------------------------------------------------------

@injected
@setup(Handler, name='synchronizeRightActions')
class SynchronizeRightActionsHandler(SynchronizeCategoryActionsHandler):
    '''
    Implementation for a processor that synchronizes the actions of the groups in the configuration file with
    the database.
    '''
    
    actionCategoryService = IActionRightService; wire.entity('actionCategoryService')
    rightService = IRightService; wire.entity('rightService')
    
    def __init__(self):
        super().__init__(Repository=RepositoryRight)
        
    def process(self, chain, solicit:Solicit, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Synchronize the actions of the groups in the configuration file with the database.
        '''
        assert isinstance(chain, Chain), 'Invalid chain %s' % chain
        assert isinstance(solicit, Solicit), 'Invalid solicit %s' % solicit
        assert isinstance(solicit.repository, RepositoryRight), 'Invalid repository %s' % solicit.repository
        
        rights = listBFS(solicit.repository, RepositoryRight.children, RepositoryRight.rightName)
        #TODO: add rightId on Repository to avoid querying the database again
        rightsIds = {e.Name: e.Id for e in [self.rightService.getById(id) for id in self.rightService.getAll()]}
        
        #group the actions by right name: rightName -> [actions]
        #TODO: duplicate logic for rights and groups - fix it (add method to parent class)
        rightActions = {}
        for right in rights:
            assert isinstance(right, RepositoryRight), 'Invalid group %s' % right
            actions = rightActions.get(rightsIds.get(right.rightName))
            if not actions: rightActions[rightsIds.get(right.rightName)] = right.actions
            else: actions.extend(right.actions)
        
        self.synchronize(rightActions)