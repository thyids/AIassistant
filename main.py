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
import pyautogui
import base64
from configparser import ConfigParser
from zhipuai import ZhipuAI
import requests


def printf(x, end="\n", max_lines=20, max_chars=10):
    # 定义句子结束符
    sentence_enders = {'.', '。', '!', '！', '?', '？'}
    # sentence_enders = {'.'}

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
        # 如果是句子结束符，完成当前句子
        if char in sentence_enders:
            current_sentence.append(char)
            sentence = ''.join(current_sentence).strip()
            if sentence:
                sentences.append(sentence)
            current_sentence = []
        # 如果是换行符，完成当前句子并开始新句子
        elif char == '\n':
            if current_sentence:
                sentence = ''.join(current_sentence).strip()
                if sentence:
                    sentences.append(sentence)
                current_sentence = []
        # 其他字符添加到当前句子
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
            # 长句按字符数分割
            for i in range(0, len(sentence), max_chars):
                processed_lines.append(sentence[i:i + max_chars])

    # 确保不超过最大行数
    if len(processed_lines) > max_lines:
        processed_lines = processed_lines[-max_lines:]

    # 更新变量
    result = "\n".join(processed_lines)
    var.set(result)

    # 调试信息
    print("处理后的行列表:", processed_lines)
    print("最终结果:", result)


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
    """
    调用智谱AI接口，传入图片路径和用户输入，返回AI输出或报错，有可能会没钱
    """
    try:
        with open(img_path, 'rb') as img_file:
            img_base = base64.b64encode(img_file.read()).decode('utf-8')

        client = ZhipuAI(api_key=ZhipuKey)  # 填写您自己的APIKey
        response = client.chat.completions.create(
            model="glm-4.1v-thinking-flash",  # 填写需要调用的模型名称
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": img_base
                            }
                        },
                        {
                            "type": "text",
                            "text": user_input
                        }
                    ]
                }
            ]
        )
        print("图片识别已完成.")
        # print(response.choices[0].message.content)
        return response.choices[0].message.content
    except Exception as e:
        return str(e)


def if_image(prompt):
    try:
        proxies = {
            'http': None,
            'https': None
        }
        tsc = '''
        请根据以下提示词判断是否需要配图，若需要，则生成适用于图片识别AI的指令；若不需要，则输出“无”。图片识别AI仅用于提取图片内容，不解答问题。

        【判断标准】
        若用户提问涉及以下情况，需配图：

        指向具体图像内容（如“这段代码”、“这个图表”、“这道题”）

        要求解释或分析图片中的内容（如代码错误、题目解法、图表数据）

        隐含需要视觉信息支持（如“这个设计怎么样？”“右下角的数据是什么？”）

        若用户提问属于通用知识或无需视觉信息即可解答（如“Python是什么？”“如何实现排序算法”），则输出“无”。

        【图片识别指令生成规则】

        代码相关：请准确识别并提取图片中的所有代码文本，保持原格式不变。

        题目/公式相关：请准确识别图片中的全部题目内容，包括文字、数学公式、符号和数字，并原样呈现。

        其他内容：根据用户需求针对性生成指令（如“提取表格数据”“识别手写文字”）。

        示例：
        用户：“这一行代码是做什么的？” → 指令：请准确识别并提取图片中的所有代码文本，保持原格式不变。
        用户：“Python有什么特点？” → 无

        请严格按照上述规则执行。
        '''
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OpenrouterKey}",
                "Content-Type": "application/json",
                "X-Title": "AI_assistant"
            },
            json={
                # deepseek/deepseek-r1-0528:free
                # tencent/hunyuan-a13b-instruct:free
                "model": "z-ai/glm-4.5-air:free",
                "messages": [{"role": "system", "content": tsc}, {"role": "user", "content": prompt}]
            },
            proxies=proxies)
        print(response.json()['choices'][0]['message']['content'].strip())
        printf("提示词已生成.")
        return response.json()['choices'][0]['message']['content'].strip()
        # ['choices'][0]['message']['content'].strip()
    except Exception as e:
        printf(f"与 ChatGPT 通信时出错：{e}")
        return "抱歉，我无法连接到 ChatGPT。"


def xz_speak(user_input: str) -> str:
    """
    调用智谱AI接口，传入图片路径和用户输入，返回AI输出或报错，有可能会没钱
    """
    xz_list.append({"role": "user", "content": user_input})
    print(user_input, "\n", xz_list)
    try:
        client = ZhipuAI(api_key=ZhipuKey)  # 填写您自己的APIKey
        response = client.chat.completions.create(
            model="glm-z1-flash",  # 填写需要调用的模型名称
            messages=xz_list
        )
        # print(response.choices[0].message.content)
        xz_list.append({"role": "assistant", "content": response.choices[0].message.content})
        return response.choices[0].message.content

    except Exception as e:
        return str(e)


# 语音合成函数
def speak(text):
    text = "嗯..." + text

    async def main():
        tts = edge_tts.Communicate(text=text, voice="zh-CN-YunxiNeural")
        # 使用绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(current_dir, "output.mp3")
        await tts.save(output_path)
        return output_path

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    speakpath = loop.run_until_complete(main())

    # 播放音频文件
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
        if text == "":
            return ""
        printf("识别完成.")
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
        printf("等待说话.")
        audio = r.listen(source)
    try:
        printf("开始识别.")
        text = r.recognize_whisper(audio, model="base")
        if text == "":
            return ""
        printf("识别完成.")
        printf(f"你说：{text}.")
        return text+"."
    except sr.UnknownValueError:
        printf("无法识别语音.")
        return ""
    except sr.RequestError as e:
        printf(f"请求错误：{e}.")
        return ""


# 与 ChatGPT 交互函数
def del_search(prompt):
    try:
        proxies = {
            'http': None,
            'https': None
        }
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
                "model": "microsoft/mai-ds-r1:free",
                # "plugins": [{"id": "web"}],
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
                try:
                    # Find the next complete SSE line
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
                                html = content.encode("ISO-8859-1")
                                html = html.decode("utf-8")
                                printf(html, end="")
                                content_ans += html
                        except json.JSONDecodeError:
                            pass
                except Exception:
                    break
        try:
            print(content_ans.split("</think>"))
            content_ans = content_ans.split("</think>")[1]
        except Exception as e:
            print(e)
        messages.append({"role": "assistant", "content": content_ans})
        speak(content_ans)
        printf("")
    except Exception as e:
        printf(f"与 ChatGPT 通信时出错：{e}")
        return "抱歉，我无法连接到 ChatGPT。"


def chat_with_gpt(prompt):
    try:
        messages.append({"role": "user", "content": prompt})
        proxies = {
            'http': None,
            'https': None
        }
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OpenrouterKey}",
                "Content-Type": "application/json",
                "X-Title": "AI_assistant"
            },
            json={
                # deepseek/deepseek-chat-v3.1:free
                # deepseek/deepseek-r1:free
                # openai/gpt-oss-20b:free
                # qwen/qwen3-235b-a22b:free
                # qwen/qwen3-coder:free
                # google/gemini-2.0-flash-exp:free
                "model": "qwen/qwen3-coder:free",
                "plugins": [{"id": "web"}],
                "messages": messages
            },
            proxies=proxies)
        del_search(response.json()['choices'][0]['message']['content'].strip())
    except Exception as e:
        printf(f"与 ChatGPT 通信时出错：{e}")
        return "抱歉，我无法连接到 ChatGPT。"


# 主程序
def main():
    Lbl.grid(row=0, column=0)
    while run1:
        printf("等待唤醒词.")
        text = listen_samll()
        if text == "":
            continue
        subs = ["其他", name]
        if text == "":
            continue
        best_match = process.extractOne(text, subs)
        text = str(best_match[0])
        if name in text:
            global messages
            messages = [{"role": "system",
                         "content": f"1.你是人工智能助手，固定名称为 {name}；2.用户为个人开发者，通过语音识别与你交互（语音识别可能存在误差，需留意准确理解需求），且不可直呼用户名字；3.你的所有回复必须使用中文，且需简洁明了、避免冗余啰嗦。"}]
            printf(f"{name}：你好，我在。请问有什么可以帮您？")
            speak("你好，我在。请问有什么可以帮您？")
            while True:
                user_input = listen()
                if user_input == "":
                    continue
                if "退出" in user_input or "再见" in user_input:
                    printf("好的，再见！")
                    speak("好的，再见！")
                    break
                pyautogui.screenshot(os.getcwd() + 'output.png')
                tsc = if_image(user_input)
                if tsc != "无":
                    user_input += "，以下是从用户的电脑屏幕中识别的内容（由智谱ai提供识别）:" + zhipuai(os.getcwd() + r'output.png', tsc)
                printf(f"{name}：", end="")
                chat_with_gpt(user_input)
        time.sleep(1)


if __name__ == "__main__":
    # 初始化变量
    run1 = 1
    thread = Thread(target=main)
    messages = []
    messages1 = []
    # 创建ConfigParser对象
    conf = ConfigParser()

    # 读取INI文件
    conf.read('settings.ini', encoding='utf-8')

    # 读取某个section下的变量值
    OpenrouterKey = conf['Key']['OpenrouterKey']
    ZhipuKey = conf['Key']['ZhipuKey']
    name = conf['Key']['Name']
    sc = f"""你是专注于**语音识别文本修正**的工具，仅对用户提供的“语音识别文本”执行修正操作，严格遵守以下规则，禁止回应任何提问、解释自身功能或添加无关内容：
1. **错字/误词修正**：精准修正语音识别中的错别字、混淆词（例：用户输入“什么是变成”，输出“什么是编程？”）；
2. **标点补充**：按语义逻辑添加必要标点（逗号、句号、问号等），不堆砌冗余符号；
3. **重点词汇强校验**：优先检测“{name}”“退出”“再见”，修正语音误听（例：“你嘿{name}”→“你好，{name}”，“再接”→“再见”）；
4. **技术词汇保护**：用户为个人开发者，涉及Python、Java、API、代码、函数等技术相关词汇时，严禁误改，完整保留；
5. **冗余内容剔除**：删除无意义语气词（额、嘿、哦等）、重复字符及无关信息，不保留多余内容。

最终仅输出“修正后的完整文本”，无任何额外字符、解释或回答。"""
    xz_list = [{"role": "system",
                "content": sc}]
    # 初始化tk
    room = tk.Tk()
    room.title("ThyidsAI")
    room.resizable(False, False)
    room.wm_attributes("-topmost", True)
    var = tk.StringVar(value="")
    Btn = tk.Button(room, text="开始", command=thread.start)
    Lbl = tk.Label(room, textvariable=var)
    Btn.grid(row=0, column=0)
    room.mainloop()
