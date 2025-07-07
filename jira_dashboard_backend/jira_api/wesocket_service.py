# jira_api/websocket_service.py
# Optional: Add WebSocket support for real-time updates

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .services import AutomationService

class AutomationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.workflow_id = self.scope['url_route']['kwargs']['workflow_id']
        self.workflow_group = f'workflow_{self.workflow_id}'
        
        # Join workflow group
        await self.channel_layer.group_add(
            self.workflow_group,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave workflow group
        await self.channel_layer.group_discard(
            self.workflow_group,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'start_automation':
            requirement = data.get('requirement')
            await self.start_automation(requirement)
    
    @database_sync_to_async
    def run_automation(self, requirement):
        service = AutomationService()
        return service.create_automated_workflow(requirement)
    
    async def start_automation(self, requirement):
        # Send initial status
        await self.send(text_data=json.dumps({
            'type': 'status',
            'message': 'Starting automation workflow...'
        }))
        
        # Run automation
        result = await self.run_automation(requirement)
        
        # Send updates as tasks are created
        if result['parent_ticket']:
            await self.send(text_data=json.dumps({
                'type': 'parent_created',
                'ticket': result['parent_ticket']
            }))
        
        for task in result['development_tasks']:
            await self.send(text_data=json.dumps({
                'type': 'task_created',
                'task': task
            }))
        
        # Send final result
        await self.send(text_data=json.dumps({
            'type': 'complete',
            'result': result
        }))