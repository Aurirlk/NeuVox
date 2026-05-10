import os, sys, traceback

os.environ['NO_PROXY'] = 'localhost,127.0.0.1,0.0.0.0'
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('ALL_PROXY', None)

try:
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Internet Settings', 0, winreg.KEY_ALL_ACCESS)
    winreg.SetValueEx(key, 'ProxyEnable', 0, winreg.REG_DWORD, 0)
    winreg.CloseKey(key)
except:
    pass

with open('test_gradio_output.log', 'w', encoding='utf-8') as f:
    try:
        import gradio as gr
        f.write(f'Gradio loaded: {gr.__version__}\n')
        f.flush()

        demo = gr.Blocks(title='test')
        with demo:
            gr.Markdown('# Test')
        f.write('Blocks created\n')
        f.flush()

        demo.launch(server_name='127.0.0.1', server_port=7861)
        f.write('Launched\n')
        f.flush()
    except Exception as e:
        f.write(f'ERROR: {e}\n')
        traceback.print_exc(file=f)
        f.flush()
