from aiogram import types, F, Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
import requests
import json
import wikipedia
from pyvis.network import Network
import networkx
import config


router = Router()

language = "ru"
wikipedia.set_lang(language)


class Form(StatesGroup):
    from_ = State()
    to_ = State()
    choice = State()
    result = State()
    prev_state = State()


@router.message(CommandStart())
async def start_handler(msg: Message, state: FSMContext) -> None:
    await state.set_state(Form.from_)
    await msg.answer(
        "Привет!\nЭтот бот поможет найти кратчайшие пути между статьями Википедии.\nВведите название статьи, с которой хотите начать поиск.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(F.text == "Искать снова")
async def again(msg: Message, state: FSMContext) -> None:
    await state.set_state(Form.from_)
    await msg.answer(
        "Отлично!\nВведите название статьи, с которой хотите начать поиск.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(Command("cancel"))
#@router.message(F.text.casefold() == "cancel")
@router.message(F.text == "Выйти")
async def cancel_handler(msg: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return

    await state.clear()
    await msg.answer(
        "Вы вышли. Ведите команду /start, чтобы начать сначала.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Form.from_)
async def from_handler(msg: Message, state: FSMContext) -> None:
    data = await state.update_data(prev_state = "from")
    data = await state.update_data(from_ = wikipedia.search(msg.text))
    titles = []
    if (len(data["from_"]) > 0):
        await state.set_state(Form.choice)
        str_ = "Выберите номер заголовка нужной статьи, с которой будет начинаться поиск:\n"
        for i in range(len(data["from_"])):
            titles.append(str(i+1) + ". " + data["from_"][i])
        await msg.answer(
            str_ + "\n".join(titles),
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await msg.answer('Похоже, по вашей теме статей не найдено.\nВозможно, вы допустили ошибку в написании? Попробуйте её исправить или выберите другую тему')

@router.message(Form.choice)
async def choice_handler(msg: Message, state: FSMContext) -> None:
    if (msg.text).isdigit():
        num = int(msg.text) - 1
    else:
        num = -1
    data = await state.get_data()
    if data["prev_state"] == "from":
        num_options = len(data["from_"])
    elif data["prev_state"] == "to":
        num_options = len(data["to_"])
    if(num >= 0 and num < num_options):
        if data["prev_state"] == "from":
            data = await state.update_data(from_=data["from_"][num])
            await state.set_state(Form.to_)
            str_ = "Вы выбрали " + data["from_"] + "\nТеперь введите название статьи, которой хотите окончить поиск."
            await msg.answer(str_, reply_markup=ReplyKeyboardRemove)
        elif data["prev_state"] == "to":
            data = await state.update_data(to_=data["to_"][num])
            str_ = "Вы выбрали " + data["to_"] + "\nИщу кратчайшие пути!"
            await msg.answer(str_)
            await find_paths(msg, data)
            await state.set_state(Form.result)
    elif num == -1:
        await msg.answer("Введите <b><u>цифру</u></b>, которая соответсвует выбранной вами статье из списка", parse_mode=ParseMode.HTML)
    else:
        await msg.answer("Похоже, вы ошиблись с выбором номера. Попробуйте ещё раз, либо введите команду /start для начала, либо введите /cancel для выхода", reply_markup=ReplyKeyboardRemove)

async def find_paths(msg: Message, data):
    title_url1 = 'https://ru.wikipedia.org/w/api.php?action=query&format=json&titles=' + data["from_"]
    id_response = requests.get(title_url1)
    id = id_response.content
    res_id = json.loads(id)
    from_page_id = list(res_id.get('query').get('pages').keys())[0]
    title_url2 = 'https://ru.wikipedia.org/w/api.php?action=query&format=json&titles=' + data["to_"]
    id_response = requests.get(title_url2)
    id = id_response.content
    res_id = json.loads(id)
    to_page_id = list(res_id.get('query').get('pages').keys())[0]
    url = config.URL_PART1 + from_page_id + config.URL_PART2 + to_page_id
    response = requests.get(url)
    paths_resp = response.content
    result = json.loads(paths_resp)
    paths = result.get('routes')
    num_paths = len(paths)

    kb = [
        [
            KeyboardButton(text="Искать снова"),
            KeyboardButton(text="Выйти")
        ],
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Что хотите сделать далее?"
    )

    if(num_paths > 0):
        paths_len = len(paths[0])
        word_path = [' путь', ' пути', ' путей']
        p_w = ""
        if num_paths % 10 == 1 and num_paths % 100 != 11:
            p_w = word_path[0]
        elif 2 <= num_paths % 10 <= 4 and (num_paths % 100 < 10 or num_paths % 100 >= 20):
            p_w = word_path[1]
        else:
            p_w = word_path[2]
        text = "От <b>" + data["from_"] + "</b> до <b>" + data["to_"] + "</b> найдено " + str(num_paths) + p_w + " длины " + str(paths_len - 1)
        await msg.answer(text, parse_mode=ParseMode.HTML)
        adj_mtrx = {}
        colors = {}
        colors_list = ['green', '#99ccff', 'yellow', 'orange', 'pink', 'red', 'magenta', 'blue']
        start = paths[0][0]
        end = paths[0][paths_len - 1]
        adj_mtrx.update({start: set()})
        colors.update({start: colors_list[0]})
        adj_mtrx.update({end: set()})
        colors.update({end: colors_list[0]})
        for path in paths:
            for i in range(1, paths_len - 1):
                if i == 1:
                    adj_mtrx.get(path[0]).add(path[i])
                    if adj_mtrx.get(path[i]) == None:
                        adj_mtrx.update({path[i]: set()})
                        colors.update({path[i]: colors_list[i]})
                else:
                    adj_mtrx.get(path[i - 1]).add(path[i])
                    if adj_mtrx.get(path[i]) == None:
                        adj_mtrx.update({path[i]: set()})
                        colors.update({path[i]: colors_list[i]})
            adj_mtrx.get(path[paths_len - 2]).add(path[paths_len - 1])

        titles_id = list(adj_mtrx.keys())
        url = "http://45.80.68.151:8000/titles/?"
        for t_id in range(len(titles_id)-1):
            p = "p=" + str(titles_id[t_id])
            url += p
            url += "&"
        p = "p=" + str(titles_id[len(titles_id) - 1])
        url += p
        response = requests.get(url)
        data = response.content
        res = json.loads(data)
        titles = res.get('result')
        for title in list(titles.keys()):
            titles[title] = titles[title].replace("\'", "")
            titles[title] = titles[title].replace("_", " ")
        for i in list(adj_mtrx.keys()):
            adj_mtrx[i] = list(adj_mtrx[i])

        data = {"token": config.TOKEN, "graph": {"edges": adj_mtrx, "directed": True, "physics": False, "labels": titles, "colors": colors}}
        response = requests.post(config.URL_UPLOAD, data=json.dumps(data)).json()
        url = config.URL_SHOW + response.get('key')
        url = "<a href='" + url + "'>Граф</a>"
        answer_string = url
        if num_paths > 5:
            answer_string += "\nПервые 5 путей:\n\n"
            str_path = ""
            for i in range(5):
                str_path = str_path + str(i + 1) + ") "
                for j in range(paths_len - 1):
                    str_path += "<a href='" + config.WIKI_URL + str(paths[i][j]) + "'>" + titles[str(paths[i][j])] + "</a>"
                    str_path += " → "
                str_path += "<a href='" + config.WIKI_URL + str(paths[i][paths_len - 1]) + "'>" + titles[str(paths[i][paths_len - 1])] + "</a>"
                str_path += "\n\n"
            answer_string += str_path
            await msg.answer(answer_string, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        else:
            answer_string += "\nПути:\n\n"
            str_path = ""
            for i in range(num_paths):
                str_path = str_path + str(i + 1) + ") "
                for j in range(paths_len - 1):
                    str_path += "<a href='" + config.WIKI_URL + str(paths[i][j]) + "'>" + titles[str(paths[i][j])] + "</a>"
                    str_path += " → "
                str_path += "<a href='" + config.WIKI_URL + str(paths[i][paths_len - 1]) + "'>" + titles[str(paths[i][paths_len - 1])] + "</a>"
                str_path += "\n\n"
            answer_string += str_path
            await msg.answer(answer_string, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            
    else:
        text = "Похоже, нельзя перейти от <b>" + data["from_"] +  "</b> до <b>" + data["to_"] + "</b> :-(\nНо вы можете попробовать поискать пути между другими статьями."
        await msg.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.message(Form.to_)
async def to_handler(msg: Message, state: FSMContext) -> None:
    data = await state.update_data(prev_state = "to")
    data = await state.update_data(to_ = wikipedia.search(msg.text))
    titles = []
    if(len(data["to_"]) > 0):
        await state.set_state(Form.choice)
        str_ = "Теперь выберите номер заголовка нужной статьи, на которой будет заканчиваться поиск:\n"
        for i in range(len(data["to_"])):
            titles.append(str(i+1) + ". " + data["to_"][i])
        await msg.answer(
            str_ + "\n".join(titles),
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await msg.answer('Похоже, по вашей теме статей не найдено.\nВозможно, вы допустили ошибку в написании? Попробуйте её исправить или выберите другую тему')


@router.message(Form.result)
async def result_handler(msg: Message):
    await msg.answer("Введите команду /start, чтобы искать снова.")
