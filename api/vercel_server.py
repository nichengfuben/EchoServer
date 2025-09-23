def handler(request):
    """最简单的 Vercel 处理函数"""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/html'},
        'body': '''
        <html>
        <head><title>Nbot Server</title></head>
        <body>
            <h1>🤖 Nbot Server Running!</h1>
            <p>Server is working on Vercel</p>
            <p><a href="/api/vercel_server">Refresh</a></p>
        </body>
        </html>
        '''
    }
