class AgentStreamClient {
    constructor() {
        this.eventSource = null;
        this.isRunning = false;
        this.generatedCode = '';
        
        this.initElements();
        this.attachEventListeners();
    }
    
    initElements() {
        // 输入元素
        this.instructionInput = document.getElementById('instruction');
        this.maxStepsInput = document.getElementById('maxSteps');
        this.modelNameInput = document.getElementById('modelName');
        this.codegenModelInput = document.getElementById('codegenModel');
        this.apiKeyInput = document.getElementById('apiKey');
        this.baseUrlInput = document.getElementById('baseUrl');
        this.codegenApiKeyInput = document.getElementById('codegenApiKey');
        this.codegenBaseUrlInput = document.getElementById('codegenBaseUrl');
        
        // 按钮
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.copyBtn = document.getElementById('copyBtn');
        this.downloadBtn = document.getElementById('downloadBtn');
        
        // 显示区域
        this.agentLog = document.getElementById('agentLog');
        this.generatedCodeEl = document.getElementById('generatedCode');
        this.statusBar = document.getElementById('status');
        this.screenshotImg = document.getElementById('currentScreenshot');
        this.screenshotContainer = document.getElementById('screenshotContainer');
    }
    
    attachEventListeners() {
        this.startBtn.addEventListener('click', () => this.start());
        this.stopBtn.addEventListener('click', () => this.stop());
        this.clearBtn.addEventListener('click', () => this.clear());
        this.copyBtn.addEventListener('click', () => this.copyCode());
        this.downloadBtn.addEventListener('click', () => this.downloadCode());
    }
    
    start() {
        // 验证输入
        const instruction = this.instructionInput.value.trim();
        const apiKey = this.apiKeyInput.value.trim();
        const baseUrl = this.baseUrlInput.value.trim();
        
        if (!instruction || !apiKey || !baseUrl) {
            alert('请填写完整的配置信息');
            return;
        }
        
        // 清空之前的内容
        this.clear();
        
        // 构建请求体
        const requestBody = {
            instruction: instruction,
            max_steps: parseInt(this.maxStepsInput.value),
            api_key: apiKey,
            base_url: baseUrl,
            model_name: this.modelNameInput.value,
            codegen_model: this.codegenModelInput.value
        };
        
        // 添加可选的代码生成配置
        const codegenApiKey = this.codegenApiKeyInput.value.trim();
        const codegenBaseUrl = this.codegenBaseUrlInput.value.trim();
        
        if (codegenApiKey) {
            requestBody.codegen_api_key = codegenApiKey;
        }
        if (codegenBaseUrl) {
            requestBody.codegen_base_url = codegenBaseUrl;
        }
        
        // 发送 POST 请求创建 SSE 连接
        fetch('/run-agent-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        }).then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 获取 ReadableStream
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            this.isRunning = true;
            this.startBtn.disabled = true;
            this.stopBtn.disabled = false;
            this.updateStatus('运行中...', 'running');
            
            // 读取流
            const processStream = ({done, value}) => {
                if (done) {
                    this.stop();
                    return;
                }
                
                // 解码数据
                const chunk = decoder.decode(value, {stream: true});
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            this.handleEvent(data);
                        } catch (e) {
                            console.error('解析事件失败:', e, line);
                        }
                    }
                }
                
                // 继续读取
                return reader.read().then(processStream);
            };
            
            // 开始处理流
            return reader.read().then(processStream);
            
        }).catch(error => {
            console.error('请求失败:', error);
            this.updateStatus('连接错误: ' + error.message, 'error');
            this.stop();
            alert('连接失败: ' + error.message);
        });
    }
    
    stop() {
        this.isRunning = false;
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        if (this.statusBar.textContent.includes('运行中')) {
            this.updateStatus('已停止', 'complete');
        }
    }
    
    clear() {
        this.agentLog.innerHTML = '';
        this.generatedCodeEl.textContent = '';
        this.generatedCode = '';
        // 清空截图
        if (this.screenshotImg) {
            this.screenshotImg.src = '';
            this.screenshotImg.alt = '当前截图';
        }
        this.updateStatus('准备就绪', '');
    }
    
    displayScreenshot(taskId, step) {
        // 通过 HTTP 请求获取截图
        if (this.screenshotImg && taskId && step) {
            const screenshotUrl = `/screenshot/${taskId}/${step}`;
            this.screenshotImg.src = screenshotUrl;
            this.screenshotImg.alt = `步骤 ${step} 截图`;
        }
    }
    
    handleEvent(event) {
        const eventType = event.event_type;
        
        switch (eventType) {
            case 'task_init':
                this.addLog('🚀 任务初始化', 'step-start');
                this.addLog(`任务 ID: ${event.task_id}`);
                break;
                
            case 'device_connected':
                this.addLog(`📱 设备已连接: ${event.data.device_model}`);
                break;
                
            case 'step_start':
                this.addLog(`▶ 步骤 ${event.step}/${event.data.total_steps} 开始`, 'step-start');
                break;
                
            case 'screenshot':
                this.addLog('📸 截图已获取');
                // 通过 HTTP 请求获取并显示截图
                this.displayScreenshot(event.task_id, event.step);
                break;
                
            case 'llm_chunk':
                // 实时显示思考过程（累加模式）
                const chunk = event.data.chunk;
                if (chunk) {
                    this.appendToLastLog(chunk, 'thinking');
                }
                break;
                
            case 'llm_complete':
                this.addLog(`✅ LLM 响应完成 (${event.data.response_length} 字符)`);
                break;
                
            case 'action_parsed':
                const action = event.data.action;
                this.addLog(`🎯 动作: ${action.action} - ${action.description || ''}`, 'action');
                break;
                
            case 'action_completed':
                this.addLog(`✅ 动作执行完成: ${event.data.status}`);
                break;
                
            case 'task_completed':
                this.addLog('🎉 Agent 任务完成!', 'step-start');
                this.addLog(`状态: ${event.data.status}, 共 ${event.data.total_steps} 步`);
                break;
                
            case 'codegen_start':
                this.addLog('📝 开始生成代码...', 'step-start');
                this.updateStatus('正在生成代码...', 'running');
                break;
                
            case 'codegen_chunk':
                // 实时追加代码
                this.generatedCode += event.data.chunk;
                this.generatedCodeEl.textContent = this.generatedCode;
                // 自动滚动到底部
                this.generatedCodeEl.scrollTop = this.generatedCodeEl.scrollHeight;
                break;
                
            case 'codegen_complete':
                this.addLog(`✅ 代码生成完成! (${event.data.code_length} 字符)`, 'step-start');
                break;
                
            case 'done':
                this.addLog('🏁 全部完成!', 'step-start');
                this.updateStatus('执行完成', 'complete');
                this.stop();
                break;
                
            case 'error':
                this.addLog(`❌ 错误: ${event.data.message}`, 'error');
                this.updateStatus('执行出错', 'error');
                break;
        }
    }
    
    addLog(message, className = '') {
        const entry = document.createElement('div');
        entry.className = `log-entry ${className}`;
        entry.textContent = message;
        this.agentLog.appendChild(entry);
        
        // 自动滚动到底部
        this.agentLog.scrollTop = this.agentLog.scrollHeight;
    }
    
    appendToLastLog(text, className = '') {
        let lastEntry = this.agentLog.lastElementChild;
        
        // 如果最后一个条目不是 thinking 类型，创建新条目
        if (!lastEntry || !lastEntry.classList.contains('thinking')) {
            lastEntry = document.createElement('div');
            lastEntry.className = `log-entry thinking`;
            lastEntry.textContent = '💭 ';
            this.agentLog.appendChild(lastEntry);
        }
        
        lastEntry.textContent += text;
        
        // 自动滚动到底部
        this.agentLog.scrollTop = this.agentLog.scrollHeight;
    }
    
    updateStatus(message, className = '') {
        this.statusBar.textContent = message;
        this.statusBar.className = `status-bar ${className}`;
    }
    
    copyCode() {
        if (!this.generatedCode) {
            alert('还没有生成代码');
            return;
        }
        
        navigator.clipboard.writeText(this.generatedCode).then(() => {
            alert('代码已复制到剪贴板');
        }).catch(err => {
            console.error('复制失败:', err);
            alert('复制失败，请手动复制');
        });
    }
    
    downloadCode() {
        if (!this.generatedCode) {
            alert('还没有生成代码');
            return;
        }
        
        const blob = new Blob([this.generatedCode], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `autojs_script_${Date.now()}.js`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// 初始化客户端
document.addEventListener('DOMContentLoaded', () => {
    new AgentStreamClient();
});
