#!/usr/bin/env python3
from src.api.main import app

print('MAIN.PY APP LOADED')
print(f'Number of routes: {len(app.routes)}')
print('First few routes:')
for i, route in enumerate(app.routes[:10]):
    methods = getattr(route, 'methods', [])
    print(f'  {i+1}. {route.path} - {list(methods)}')

# Look specifically for ai-tools routes
ai_tools_routes = [route for route in app.routes if 'ai-tools' in route.path]
print(f'\nAI Tools routes found: {len(ai_tools_routes)}')
for route in ai_tools_routes:
    methods = getattr(route, 'methods', [])
    print(f'  {route.path} - {list(methods)}')