# coding=utf-8
import json
import speech_recognition as sr
import edge_tts
import asyncio
import os
import tkinter as tk
from tkinter import messagebox as msg
import pyautogui as pag
import pyperclip
from threading import Thread
from fuzzywuzzy import process
from playsound import playsound
import time
import base64
from configparser import ConfigParser
from zhipuai import ZhipuAI
import requests


def printf(x, end="\n", max_lines=20, max_chars=10):
    # 定义句子结束符
    sentence_enders = {'.', '。', '!', '！', '?', '？'}
    # 获取当前内容并添加新内容，先清理多余的换行符
    current_content = var.get()
    new_content = current_content + x.strip() + end

    # 清理连续的换行符，只保留一个
    while "\n\n" in new_content:
        new_content = new_content.replace("\n\n", "\n")

    # 第一步：按标点和换行分割成完整句子
    sentences = []
    current_sentence = []
    for char in new_content:
        if char in sentence_enders:
            current_sentence.append(char)
            sentence = ''.join(current_sentence).strip()
            if sentence:
                sentences.append(sentence)
            current_sentence = []
        elif char == '\n':
            if current_sentence:
                sentence = ''.join(current_sentence).strip()
                if sentence:
                    sentences.append(sentence)
                current_sentence = []
        else:
            current_sentence.append(char)
    # 添加最后一个句子（如果有）
    if current_sentence:
        sentence = ''.join(current_sentence).strip()
        if sentence:
            sentences.append(sentence)

    # 第二步：处理每个句子，长句分割，短句保留
    processed_lines = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            processed_lines.append(sentence)
        else:
            for i in range(0, len(sentence), max_chars):
                processed_lines.append(sentence[i:i + max_chars])

    # 确保不超过最大行数
    if len(processed_lines) > max_lines:
        processed_lines = processed_lines[-max_lines:]

    # 更新变量
    result = "\n".join(processed_lines)
    var.set(result)


def do(i, *args):
    # 在指定位置点击
    if i == 0:
        pag.moveTo(args[0], args[1])
        pag.click()
    # 输入特定内容
    elif i == 1:
        pyperclip.copy(args[0])
        pag.hotkey("ctrl", "v")
    # 输入键
    elif i == 2:
        size = len(args)
        if size == 1:
            pag.press(args[0])
        elif size == 2:
            pag.hotkey(args[0], args[1])
        elif size == 3:
            pag.hotkey(args[0], args[1], args[2])
        elif size == 4:
            pag.hotkey(args[0], args[1], args[2], args[3])


def zhipuai(img_path: str, user_input: str) -> str:
    """调用智谱AI接口识别图片内容"""
    try:
        with open(img_path, 'rb') as img_file:
            img_base = base64.b64encode(img_file.read()).decode('utf-8')

        client = ZhipuAI(api_key=ZhipuKey)
        response = client.chat.completions.create(
            model="glm-4.1v-thinking-flash",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": img_base}},
                        {"type": "text", "text": user_input}
                    ]
                }
            ]
        )
        printf("图片识别已完成.")
        return response.choices[0].message.content
    except Exception as e:
        return f"图片识别错误：{str(e)}"


def if_image(prompt):
    """
    扩展功能：同时判断是否需要配图和电脑操控，返回JSON格式结果
    返回结构：{"img_tsc": 图片识别指令/无, "control_cmds": 操控指令列表/无}
    """
    try:
        proxies = {'http': None, 'https': None}
        # 扩展后的系统提示词：新增电脑操控判断和指令生成规则
        tsc = '''
请根据用户提示词判断两项内容：1. 是否需要配图（图片识别仅提取内容）；2. 是否需要电脑自动操控（点击/输入/按键）。
输出严格为JSON字符串，包含"img_tsc"和"control_cmds"两个字段：
- "img_tsc"：需配图则按规则生成指令，否则为"无"；
- "control_cmds"：需操控则生成结构化指令列表，否则为"无"。

【配图判断标准】
需配图场景：
1. 指向具体图像内容（如“这段代码”“这个图表”）；
2. 要求分析图片内容（如代码错误、题目解法）；
3. 隐含视觉需求（如“这个设计怎么样”）。
无需则"img_tsc"为"无"。

【电脑操控判断标准】
需操控场景：
1. 明确要求点击屏幕位置（如“点击浏览器关闭按钮”）；
2. 明确要求输入文本（如“在记事本输入Hello”）；
3. 明确要求按键/组合键（如“按Ctrl+S保存”）；
4. 隐含操控需求（如“打开记事本”“关闭当前窗口”）。
无需则"control_cmds"为"无"。

【图片识别指令规则】
- 代码：提取所有代码文本，保持原格式；
- 题目：提取完整题目（含公式/符号）；
- 其他：按需求生成（如“提取表格数据”）。

【电脑操控指令规则】
操控指令为JSON数组，每个元素格式：
{
  "i": 操作类型（0=点击，1=输入文本，2=按键/组合键）,
  "args": 参数列表（按类型匹配）
}
- 类型0：args=[x,y]（屏幕坐标，像素，左上角为原点，需在屏幕范围内）；
- 类型1：args=[text]（需输入的完整内容）；
- 类型2：args=[key1,key2...]（按键名，如"ctrl""enter""f5"）。

【输出要求】
1. 仅输出JSON，无额外字符；
2. 确保操控指令可行（坐标合法、按键正确）；
3. 无需配图和操控则输出{"img_tsc":"无","control_cmds":"无"}。

示例：
1. 用户：“点击屏幕(100,200)的记事本图标”
输出：{"img_tsc":"无","control_cmds":[{"i":0,"args":[100,200]}]}
2. 用户：“这行代码什么意思？”
输出：{"img_tsc":"请提取图片中所有代码文本并保持原格式","control_cmds":"无"}
3. 用户：“在记事本输入Python，按Ctrl+S保存”
输出：{"img_tsc":"无","control_cmds":[{"i":1,"args":["Python"]},{"i":2,"args":["ctrl","s"]}]}
        '''
        response = requests.post(
            url="https://api.deepseek.com/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DeepseekKey}",
                "Content-Type": "application/json",
                "X-Title": "AI_assistant"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "system", "content": tsc}, {"role": "user", "content": prompt}]
            },
            proxies=proxies)

        response_json = response.json()
        print(response_json["choices"][0]["message"]["content"].strip())
        if "choices" not in response_json or not response_json["choices"]:
            printf("未获取到有效操控判断结果.")
            return json.dumps({"img_tsc": "无", "control_cmds": "无"})

        ai_content = response_json["choices"][0]["message"]["content"].strip()
        # 验证并解析AI返回的JSON
        try:
            result = json.loads(ai_content)
            # 检查必要字段
            if not all(k in result for k in ["img_tsc", "control_cmds"]):
                printf("AI返回JSON缺少必要字段.")
                return json.dumps({"img_tsc": "无", "control_cmds": "无"})
            printf("配图与操控需求判断完成.")
            return json.dumps(result)
        except json.JSONDecodeError:
            printf("AI返回内容不是有效JSON，默认无需操控.")
            return json.dumps({"img_tsc": "无", "control_cmds": "无"})
    except Exception as e:
        printf(f"判断配图与操控需求出错：{e}.")
        return json.dumps({"img_tsc": "无", "control_cmds": "无"})


def xz_speak(user_input: str) -> str:
    """语音识别文本修正"""
    xz_list.append({"role": "user", "content": user_input})
    try:
        client = ZhipuAI(api_key=ZhipuKey)
        response = client.chat.completions.create(
            model="glm-4.5-flash",
            messages=xz_list
        )
        ans = response.choices[0].message.content
        xz_list.append({"role": "assistant", "content": ans})
        return ans
    except Exception as e:
        return f"文本修正错误：{str(e)}"


# 语音合成函数
def speak(text):
    text = "嗯..." + text

    async def main():
        tts = edge_tts.Communicate(text=text, voice="zh-CN-YunxiNeural")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(current_dir, "output.mp3")
        await tts.save(output_path)
        return output_path

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    speakpath = loop.run_until_complete(main())
    playsound(speakpath)


# 语音识别函数
def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        printf("等待说话.")
        audio = r.listen(source)
    try:
        printf("开始识别.")
        text = r.recognize_whisper(audio, model="base")
        if not text:
            return ""
        printf("开始修正.")
        text = xz_speak(text)
        printf("修正完成.")
        printf(f"你说：{text}.")
        return text
    except sr.UnknownValueError:
        printf("无法识别语音.")
        return ""
    except sr.RequestError as e:
        printf(f"请求错误：{e}.")
        return ""


# 语音识别函数(阉割版)
def listen_samll():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        printf("等待唤醒词.")
        audio = r.listen(source)
    try:
        printf("开始识别.")
        text = r.recognize_whisper(audio, model="base")
        if not text:
            return ""
        printf("识别完成.")
        printf(f"你说：{text}.")
        return text + "."
    except sr.UnknownValueError:
        printf("无法识别语音.")
        return ""
    except sr.RequestError as e:
        printf(f"请求错误：{e}.")
        return ""


# 与OpenRouter交互函数
def del_search(prompt):
    try:
        proxies = {'http': None, 'https': None}
        tsc = """用户会给你一段包含markdown格式的AI回答，请你将其中所有markdown格式标记完全清除，包括但不限于：
1. 粗体标记**和__
2. 斜体标记*和_
3. 列表标记（包括*、-、+及后续空格）
4. 代码标记`和```
5. 标题标记#及后续空格
6. 引用标记>及后续空格
7. 链接标记[文本](链接)（仅保留文本部分，去除[、]、(、)及链接）
8. 特殊标记<｜begin▁of▁sentence｜>等

处理要求：
- 仅去除格式标记，保留原始文本内容和语义
- 确保去除标记后语句通顺，无多余空格或符号
- 保持原有段落结构和换行逻辑

示例：
用户输入：Python是一种高级编程语言，它具有以下特点：[python.org][https://www.python.org/download]\n\n*   **解释型:** Python代码不需要编译，可以直接运行. \n*   **面向对象:**\nPython支持面向对象编程. \n*   `高层级`: Python具有内置的高级数据结构.<｜begin▁of▁sentence｜>
你需输出：Python是一种高级编程语言，它具有以下特点：\n\n解释型: Python代码不需要编译，可以直接运行. \n面向对象:\nPython支持面向对象编程. \n高层级: Python具有内置的高级数据结构."""
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OpenrouterKey}",
                "Content-Type": "application/json",
                "X-Title": "AI_assistant"
            },
            json={
                "model": "qwen/qwen3-235b-a22b:free",
                "stream": True,
                "messages": [{"role": "system", "content": tsc}, {"role": "user", "content": prompt}]
            },
            proxies=proxies,
            stream=True)

        content_ans = ""
        buffer = ""
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            buffer += chunk
            while True:
                line_end = buffer.find('\n')
                if line_end == -1:
                    break
                line = buffer[:line_end].strip()
                buffer = buffer[line_end + 1:]
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        data_obj = json.loads(data)
                        content = data_obj["choices"][0]["delta"].get("content")
                        if content:
                            content = content.encode("ISO-8859-1").decode("utf-8")
                            printf(content, end="")
                            content_ans += content
                    except json.JSONDecodeError:
                        pass
        messages.append({"role": "assistant", "content": content_ans})
        print(content_ans)
        speak(content_ans)
        printf("")
    except Exception as e:
        printf(f"与AI通信出错：{e}")


def chat_with_gpt(prompt):
    try:
        messages.append({"role": "user", "content": prompt})
        proxies = {'http': None, 'https': None}
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OpenrouterKey}",
                "Content-Type": "application/json",
                "X-Title": "AI_assistant"
            },
            json={
                "model": "qwen/qwen3-coder:free",
                "plugins": [{"id": "web"}],
                "messages": messages
            },
            proxies=proxies)
        del_search(response.json()['choices'][0]['message']['content'].strip())
    except Exception as e:
        printf(f"与AI通信出错：{e}")


# 主程序
def main():
    Lbl.grid(row=0, column=0)
    while run1:
        printf("等待唤醒词.")
        text = listen_samll()
        if not text:
            continue
        best_match = process.extractOne(text, ["其他", name])
        if name in str(best_match[0]):
            global messages
            messages = [{"role": "system",
                         "content": f"1.你是人工智能助手，固定名称为 {name}；2.用户为个人开发者，通过语音识别与你交互（语音识别可能存在误差，需留意准确理解需求），且不可直呼用户名字；3.你的所有回复必须使用中文，且需简洁明了、避免冗余啰嗦。"}]
            printf(f"{name}：你好，我在。请问有什么可以帮您？")
            speak("你好，我在。请问有什么可以帮您？")
            while True:
                user_input = listen()
                if not user_input:
                    continue
                if "退出" in user_input or "再见" in user_input:
                    printf("好的，再见！")
                    speak("好的，再见！")
                    break

                # 1. 调用if_image获取配图和操控需求
                if_result_str = if_image(user_input)
                try:
                    if_result = json.loads(if_result_str)
                    img_tsc = if_result.get("img_tsc", "无")
                    control_cmds = if_result.get("control_cmds", "无")
                except json.JSONDecodeError as e:
                    printf(f"解析需求结果失败：{e}")
                    img_tsc = "无"
                    control_cmds = "无"

                # 2. 处理图片识别（原逻辑）
                if img_tsc != "无":
                    screenshot_path = os.path.join(os.getcwd(), "output.png")
                    pag.screenshot(screenshot_path)
                    img_content = zhipuai(screenshot_path, img_tsc)
                    user_input += f"，以下是屏幕识别内容：{img_content}"

                # 3. 处理电脑操控（新增逻辑）
                def execute_control():
                    """主线程执行操控确认和指令执行"""
                    if control_cmds == "无" or not isinstance(control_cmds, list):
                        return
                    # 生成操控说明用于弹窗
                    control_desc = "\n".join([
                        f"操作{i + 1}：{['点击', '输入文本', '按键'][cmd['i']]} → 参数：{cmd['args']}"
                        for i, cmd in enumerate(control_cmds) if cmd.get("i") in [0, 1, 2]
                    ])
                    # 弹窗询问用户
                    agree = msg.askyesno(
                        "电脑操控确认",
                        f"检测到需要以下电脑操控操作，是否允许执行？\n\n{control_desc}\n\n注意：执行后可能影响当前操作！"
                    )
                    if not agree:
                        printf("用户拒绝电脑操控")
                        return
                    # 执行操控指令
                    screen_w, screen_h = pag.size()  # 获取屏幕分辨率
                    for cmd in control_cmds:
                        try:
                            i = cmd.get("i")
                            args = cmd.get("args", [])
                            # 验证操作类型和参数
                            if i not in [0, 1, 2]:
                                print(f"无效操作类型{i}，跳过")
                                continue
                            # 点击操作：验证坐标范围
                            if i == 0:
                                if len(args) != 2:
                                    print(f"点击需2个坐标参数，实际{len(args)}个，跳过")
                                    continue
                                x, y = args
                                if x < 0 or x > screen_w or y < 0 or y > screen_h:
                                    print(f"坐标({x},{y})超出屏幕范围({screen_w}x{screen_h})，跳过")
                                    continue
                            # 输入操作：验证参数数量
                            elif i == 1:
                                if len(args) != 1:
                                    print(f"输入需1个文本参数，实际{len(args)}个，跳过")
                                    continue
                            # 按键操作：验证参数数量
                            elif i == 2:
                                if len(args) < 1:
                                    print(f"按键需至少1个参数，实际{len(args)}个，跳过")
                                    continue
                            # 执行操作
                            do(i, *args)
                            printf(f"成功执行操作：类型{i}，参数{args}")
                            time.sleep(0.8)  # 间隔0.8秒避免操作冲突
                        except Exception as e:
                            printf(f"执行操作{cmd}失败：{e}")

                # 让主线程执行操控逻辑（避免tkinter线程安全问题）
                room.after(0, execute_control)

                # 4. 与AI交互（原逻辑）
                printf(f"{name}：", end="")
                chat_with_gpt(user_input)
        time.sleep(1)


if __name__ == "__main__":
    # 初始化全局变量
    run1 = 1
    thread = Thread(target=main)
    messages = []
    # 读取配置文件
    conf = ConfigParser()
    conf.read('settings.ini', encoding='utf-8')
    OpenrouterKey = conf['Key']['OpenrRuterKey']
    ZhipuKey = conf['Key']['ZhiPuKey']
    DeepseekKey = conf['Key']['DeepseekKey']
    name = conf['Key']['Name']
    # 语音修正系统提示
    xz_sc = f"""你是专注于**语音识别文本修正**的工具，仅对用户提供的“语音识别文本”执行修正操作，严格遵守以下规则，禁止回应任何提问、解释自身功能或添加无关内容：
1. **错字/误词修正**：精准修正语音识别中的错别字、混淆词以及用户让ai干某些操作电脑的词语识别成现实的（通常在打开，写等动词后面，如记事本识别成笔记本）（例：用户输入“什么是变成”，输出“什么是编程？”,用户输入“打开笔记本，输入python”，输出“打开记事本，输入python。”）；
2. **标点补充**：按语义逻辑添加必要标点（逗号、句号、问号等），不堆砌冗余符号；
3. **重点词汇强校验**：优先检测“{name}”“退出”“再见”，修正语音误听（例：“你嘿{name}”→“你好，{name}”）；
4. **技术词汇保护**：用户为个人开发者，涉及Python、Java、API、代码、函数等技术相关词汇时，严禁误改，完整保留；
5. **冗余内容剔除**：删除无意义语气词（额、嘿、哦等）、重复字符及无关信息，不保留多余内容。

最终仅输出“修正后的完整文本”，无任何额外字符、解释或回答。"""
    xz_list = [{"role": "system", "content": xz_sc}]
    # 初始化TK界面
    room = tk.Tk()
    room.title("ThyidsAI")
    room.resizable(False, False)
    room.wm_attributes("-topmost", True)
    var = tk.StringVar(value="")
    Btn = tk.Button(room, text="开始", command=thread.start)
    Lbl = tk.Label(room, textvariable=var, wraplength=300)  # 增加换行长度
    Btn.grid(row=0, column=0, padx=5, pady=5)
    Lbl.grid(row=1, column=0, padx=5, pady=5)
    # 启动主循环
    room.mainloop()
    run1 = 0  # 停止子线程

    exit()
