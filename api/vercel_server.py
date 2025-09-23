# api/vercel_server.py
import json

def handler(request, context=None):
    """最简单的测试版本"""
    try:
        print("=== 函数开始执行 ===")  # 这行会在日志中显示
        
        # 基本的响应
        response = {
            'status': 'success',
            'message': 'Nbot Server is working!',
            'path': request.path,
            'method': request.method
        }
        
        print("=== 函数执行成功 ===")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response)
        }
        
    except Exception as e:
        print(f"=== 错误信息: {str(e)} ===")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

# 本地测试
if __name__ == '__main__':
    class MockRequest:
        def __init__(self, method='GET', path='/', body=b''):
            self.method = method
            self.path = path
            self.body = body
    
    # 测试函数
    test_request = MockRequest()
    result = handler(test_request)
    print("测试结果:", result)
