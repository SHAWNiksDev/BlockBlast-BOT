"""Shared live UI translations. Keys and interpolation are identical in every locale."""
ROWS = [
('screen_mode','Распознавание по экрану','Screen recognition','Розпізнавання за екраном'),
('retry_finished','Жесты не подтверждены. Проверьте экран и запустите бота заново.','Gestures were not confirmed. Check the screen and start the bot again.','Жести не підтверджено. Перевірте екран і запустіть бота знову.'),
('empty_tray_finished','Лоток остаётся пустым. Проверьте игру и запустите бота заново.','The tray remains empty. Check the game and start the bot again.','Лоток залишається порожнім. Перевірте гру і запустіть бота знову.'),
('new_game_finished','Обнаружена новая партия. Запустите бота заново.','A new game was detected. Start the bot again.','Виявлено нову партію. Запустіть бота знову.'),
('position_changed_finished','Позиция изменилась во время паузы. Запустите бота заново.','The position changed during the pause. Start the bot again.','Позиція змінилася під час паузи. Запустіть бота знову.'),
('storage_warning','Запись истории отключена: достигнут лимит или хранилище недоступно. Игра продолжается.','History recording is disabled: the limit was reached or storage is unavailable. Play continues.','Запис історії вимкнено: досягнуто ліміт або сховище недоступне. Гра триває.'),
('board_resync','Поле изменилось в игре: позиция распознана заново, план пересчитан.','The board changed in the game: position recognized again, plan recalculated.','Поле змінилося у грі: позицію розпізнано знову, план перераховано.'),
('waiting_start','Ожидание начала партии','Waiting to start a game','Очікування початку партії'),
('waiting_adb','Готово · Ожидание ADB','Ready · Waiting for ADB','Готово · Очікування ADB'),
('reset_category','Сбросить только открытую категорию. Остальные разделы и файлы калибровки не изменятся.','Reset only the current category. Other sections and calibration files are preserved.','Скинути лише відкриту категорію. Інші розділи та файли калібрування не зміняться.'),
('browse_profile','Выбрать профиль телефона','Choose phone profile','Вибрати профіль телефона'),
('json_files','Профили JSON (*.json)','JSON profiles (*.json)','Профілі JSON (*.json)'),
('profile_valid','Профиль найден · JSON корректен','Profile found · valid JSON','Профіль знайдено · JSON коректний'),
('profile_invalid','Выберите существующий профиль JSON','Select an existing JSON profile','Виберіть наявний профіль JSON'),

('device_busy','Телефон уже управляется другим экземпляром BlockBlast BOT. Сначала остановите его.','This phone is controlled by another BlockBlast BOT instance. Stop it first.','Телефоном уже керує інший екземпляр BlockBlast BOT. Спочатку зупиніть його.'),('adb_timeout','ADB не ответил за 8 секунд. Проверьте подключение.','ADB did not respond in 8 seconds. Check the connection.','ADB не відповів за 8 секунд. Перевірте підключення.'),('adb_missing','ADB не найден. Проверьте комплектность portable-папки.','ADB not found. Check that the portable folder is complete.','ADB не знайдено. Перевірте комплектність portable-папки.'),('profile_resolution','Разрешение экрана отличается от профиля. Выберите подходящий профиль.','Screen resolution differs from the profile. Select a matching profile.','Роздільна здатність екрана відрізняється від профілю. Виберіть відповідний профіль.'),
('board_not_found','Откройте классическое поле Block Blast.','Open the classic Block Blast board.','Відкрийте класичне поле Block Blast.'),('screen_obscured','Поле закрыто меню или анимацией. Бот ждёт доступный экран.','Board obscured by a menu or animation. Waiting for a clear screen.','Поле закрите меню або анімацією. Бот очікує доступний екран.'),('stream_error','Не удалось получить кадры. Проверьте телефон и подключение.','Could not receive frames. Check the phone and connection.','Не вдалося отримати кадри. Перевірте телефон і підключення.'),('recognition_error','Фигура не распознана. Проверьте экран и профиль телефона.','Piece not recognized. Check the screen and phone profile.','Фігуру не розпізнано. Перевірте екран і профіль телефона.'),
('game','Игра','Game','Гра'),('settings','Настройки','Settings','Налаштування'),('history','История','History','Історія'),
('start','Начать','Start','Почати'),('pause','Пауза','Pause','Пауза'),('resume','Продолжить','Resume','Продовжити'),('stop','Остановить','Stop','Зупинити'),('refresh','Обновить','Refresh','Оновити'),
('ready','Готово','Ready','Готово'),('connecting','Подключаю телефон…','Connecting to phone…','Підключаю телефон…'),('stopping','Останавливаю…','Stopping…','Зупиняю…'),
('phone','Экран телефона','Phone screen','Екран телефона'),('current','Текущая партия','Current game','Поточна партія'),('board','Распознанное поле','Recognized board','Розпізнане поле'),
('score','Очки','Score','Бали'),('best','Рекорд','Best score','Рекорд'),('moves','Ходы','Moves','Ходи'),('lines','Линии','Lines','Лінії'),('attempts','Попытки','Attempts','Спроби'),
('events','События','Events','Події'),('clear','Очистить журнал','Clear events','Очистити журнал'),('debug','Диагностика','Diagnostics','Діагностика'),
('no_phone','Телефон не подключён','No phone connected','Телефон не підключено'),('connect_hint','Подключите телефон по USB и разрешите отладку.','Connect your phone via USB and allow debugging.','Підключіть телефон через USB і дозвольте налагодження.'),
('preview_hint','Нажмите «Начать», чтобы увидеть экран.','Press Start to view the screen.','Натисніть «Почати», щоб побачити екран.'),('phone_ready','Телефон подключён','Phone connected','Телефон підключено'),
('live','Прямой эфир','Live view','Прямий ефір'),('last_frame','Последний кадр','Last frame','Останній кадр'),('verified','Ходы проверяются по экрану','Moves verified on screen','Ходи перевіряються за екраном'),
('board_hint','Выберите телефон и начните игру.','Select a phone and start a game.','Виберіть телефон і почніть гру.'),('queue','Текущие фигуры','Current pieces','Поточні фігури'),
('tempo','{rate} ход/мин · попыток: {attempts} · отказов: {rejected}','{rate} moves/min · attempts: {attempts} · rejected: {rejected}','{rate} ход/хв · спроб: {attempts} · відмов: {rejected}'),
('empty_events','Здесь появятся ходы, паузы и результат партии.','Moves, pauses and the game result will appear here.','Тут з’являться ходи, паузи та результат партії.'),
('appearance','Интерфейс','Appearance & language','Інтерфейс'),('language','Язык приложения','App language','Мова застосунку'),('language_hint','Изменяется сразу, без перезапуска.','Applies immediately, without a restart.','Змінюється одразу, без перезапуску.'),
('theme','Цветовая тема','Color theme','Колірна тема'),('dark','Тёмная','Dark','Темна'),('light','Светлая','Light','Світла'),('theme_toggle','Сменить тему','Switch theme','Змінити тему'),
('appearance_hint','Тема и язык доступны даже во время игры.','Theme and language can be changed during a game.','Тему й мову можна змінювати під час гри.'),
('session','Партия','Game session','Партія'),('strategy','Стратегия','Strategy','Стратегія'),('screen','Экран и точность','Screen & precision','Екран і точність'),('storage','История и файлы','History & files','Історія та файли'),
('settings_title','Настройте под себя','Make it yours','Налаштуйте під себе'),('settings_hint','Темп автоматический. Параметры игры применяются к следующей партии.','Speed is automatic. Game settings apply to the next session.','Темп автоматичний. Ігрові параметри застосовуються до наступної партії.'),
('locked','Партия идёт: игровые настройки заблокированы, включая паузу. Тему и язык можно менять.','Game settings are locked until the session ends, including while paused. Appearance is available.','Ігрові налаштування заблоковані до завершення партії, зокрема на паузі. Інтерфейс доступний.'),
('reset','Сбросить','Reset','Скинути'),('save','Сохранить','Save','Зберегти'),('saved','Все изменения сохранены','All changes saved','Усі зміни збережено'),('unsaved','Есть несохранённые изменения','Unsaved changes','Є незбережені зміни'),
('settings_error','Проверьте настройки перед запуском.','Check your settings before starting.','Перевірте налаштування перед запуском.'),('save_error','Не удалось сохранить настройки. Проверьте доступ к файлу.','Could not save settings. Check file access.','Не вдалося зберегти налаштування. Перевірте доступ до файлу.'),
('unlimited','Без лимита','Unlimited','Без обмежень'),('auto','Автоматически','Automatic','Автоматично'),('stream','Видеопоток','Video stream','Відеопотік'),('screenshot','Скриншоты','Screenshots','Знімки екрана'),
('max_moves','Лимит ходов','Move limit','Ліміт ходів'),('auto_pause','Автоматическая пауза','Automatic pause','Автоматична пауза'),('read_score','Очки и рекорд','Read scores','Зчитувати бали'),('score_every','Читать счёт каждые N ходов','Read score every N moves','Зчитувати бали кожні N ходів'),
('beam','Ширина поиска','Search width','Ширина пошуку'),('max_rejections','Предел отказов','Rejection limit','Ліміт відмов'),('capture','Источник кадров','Capture source','Джерело кадрів'),('stream_width','Ширина потока, px','Stream width, px','Ширина потоку, px'),('stream_fps','Кадров в секунду','Frames per second','Кадрів за секунду'),
('stable_frames','Кадров для подтверждения','Confirmation frames','Кадрів для підтвердження'),('settle_time','Стабильность фигуры, с','Piece stability, s','Стабільність фігури, с'),('verify_timeout','Проверка жеста, с','Gesture verification, s','Перевірка жесту, с'),('animation_timeout','Ожидание анимации, с','Animation wait, s','Очікування анімації, с'),('profile','Профиль телефона','Phone profile','Профіль телефона'),
('console_logs','Показывать события','Show events','Показувати події'),('file_logs','Полная история','Full history','Повна історія'),('save_screenshots','Сохранять изображения','Save screenshots','Зберігати знімки'),('max_sessions','Хранить партий','Sessions to keep','Зберігати партій'),('max_history_mb','Лимит истории, МБ','History limit, MB','Ліміт історії, МБ'),('max_screenshots','Изображений на партию','Screenshots per session','Знімків на партію'),('max_log_mb','Размер журнала, МБ','Log size, MB','Розмір журналу, МБ'),('show_board','Поле в консольном режиме','Board in console mode','Поле в консольному режимі'),
('hint_max_moves','0 — до завершения партии или ручной остановки.','0 means until game over or manual stop.','0 — до завершення партії або ручної зупинки.'),('hint_auto_pause','Ждать при выходе из игры, блокировке и открытии шторки.','Wait when the game is hidden, the phone is locked or the shade is open.','Чекати після виходу з гри, блокування або відкриття шторки.'),('hint_read_score','Распознавать числа на экране телефона.','Recognize score numbers on the phone screen.','Розпізнавати числа на екрані телефона.'),('hint_score_every','Фоновое обновление не задерживает ходы.','Background score updates do not delay moves.','Фонове оновлення не затримує ходи.'),('hint_beam','Больше вариантов — дольше расчёт.','More alternatives take longer to evaluate.','Більше варіантів — довше обчислення.'),('hint_max_rejections','После нескольких отказов бот безопасно приостановится.','Repeated failures safely pause the bot.','Після кількох відмов бот безпечно призупиниться.'),('hint_file_logs','Результаты, время и полная последовательность действий.','Results, times and a complete action timeline.','Результати, час і повна послідовність дій.'),('hint_save_screenshots','Только при включённой полной истории. Иначе кадры остаются в памяти.','Requires full history. Otherwise frames stay in memory.','Потрібна повна історія. Інакше кадри залишаються в пам’яті.'),('hint_profile','Калибровка координат для вашего устройства.','Coordinate calibration for your device.','Калібрування координат для вашого пристрою.'),
('history_search','Поиск по действиям партии…','Search session actions…','Пошук дій партії…'),('history_count','Партий: {count} · лимит: {limit} · до {mb} МБ','Sessions: {count} · limit: {limit} · up to {mb} MB','Партій: {count} · ліміт: {limit} · до {mb} МБ'),('no_history','Сохранённых партий пока нет','No saved sessions yet','Збережених партій поки немає'),
('history_item','{score} очков · {moves} ходов · {duration}','{score} points · {moves} moves · {duration}','{score} балів · {moves} ходів · {duration}'),('session_summary','Сводка партии','Session summary','Підсумок партії'),('timeline','Хронология действий','Action timeline','Хронологія дій'),('status','Статус','Status','Статус'),('duration','Длительность','Duration','Тривалість'),('started','Начало','Started','Початок'),('ended','Завершение','Ended','Завершення'),('pauses','Паузы','Paused time','Час пауз'),('unknown','Не записано','Not recorded','Не записано'),('filtered','Показано: {shown} из {total}','Showing {shown} of {total}','Показано: {shown} із {total}'),('archive_old','Архив старой версии: часть действий могла не сохраниться.','Older archive: some actions may not have been retained.','Архів старої версії: частина дій могла не зберегтися.'),
('devices','Устройств: {count}','Devices: {count}','Пристроїв: {count}'),('scanning','Поиск устройств…','Looking for devices…','Пошук пристроїв…'),('working','Бот играет','Bot is playing','Бот грає'),
('event_move','Ход','Move','Хід'),('event_attempt','Попытка','Attempt','Спроба'),('event_pause','Пауза','Pause','Пауза'),('event_error','Ошибка','Error','Помилка'),('event_rejected','Отказ','Rejected','Відмова'),('event_info','Событие','Event','Подія'),('event_debug','Замер','Timing','Вимір'),
('move_text','Ход {move}: фигура {slot} → строка {row}, столбец {col} · линий: {lines} · очки: {score}','Move {move}: piece {slot} → row {row}, column {col} · lines: {lines} · score: {score}','Хід {move}: фігура {slot} → рядок {row}, стовпець {col} · ліній: {lines} · бали: {score}'),
('attempt_text','Попытка {attempt}: фигура {slot} → строка {row}, столбец {col}','Attempt {attempt}: piece {slot} → row {row}, column {col}','Спроба {attempt}: фігура {slot} → рядок {row}, стовпець {col}'),
('start_text','Начало партии','Session started','Початок партії'),('summary_text','Завершение: {reason}','Finished: {reason}','Завершення: {reason}'),('paused_text','Пауза: {reason}','Paused: {reason}','Пауза: {reason}'),('resumed_text','Продолжение после паузы {duration}','Resumed after {duration}','Продовжено після паузи {duration}'),('rejected_text','Жест не принят · попытка {attempt}','Gesture rejected · attempt {attempt}','Жест не прийнято · спроба {attempt}'),
('motion_text','Проверка жеста: {reason} · поправок: {count}','Gesture check: {reason} · corrections: {count}','Перевірка жесту: {reason} · виправлень: {count}'),('timing_text','Время выполнения жеста: {seconds} с','Gesture duration: {seconds} s','Час виконання жесту: {seconds} с'),('timing_cycle_text','Ход: чтение {read} с · план {plan} с · жест {gesture} с · проверка {verify} с','Move: read {read} s · plan {plan} s · gesture {gesture} s · verify {verify} s','Хід: читання {read} с · план {plan} с · жест {gesture} с · перевірка {verify} с'),('resync','После паузы поле распознано заново','Board recognized again after pause','Після паузи поле розпізнано заново'),('tray_resync','Фигуры обновлены, план пересчитан','Pieces updated, plan recalculated','Фігури оновлено, план перераховано'),('unstable','Ожидание стабильного игрового поля','Waiting for a stable board','Очікування стабільного ігрового поля'),('capture_fallback','Видеопоток недоступен, используются скриншоты','Stream unavailable, using screenshots','Відеопотік недоступний, використовуються знімки'),
('finished','Завершено','Finished','Завершено'),('no_moves','Нет доступных ходов','No legal moves','Немає доступних ходів'),('limit_reached','Достигнут лимит ходов','Move limit reached','Досягнуто ліміту ходів'),('user_stop','Остановлено пользователем','Stopped by user','Зупинено користувачем'),('manual_pause','Пауза по кнопке','Paused by user','Пауза користувачем'),('screen_locked','Экран заблокирован или выключен','Screen locked or off','Екран заблоковано або вимкнено'),('shade_open','Открыта шторка уведомлений','Notification shade is open','Відкрито шторку сповіщень'),('wait_game','Ожидаю возвращения в Block Blast','Waiting for Block Blast','Очікую повернення до Block Blast'),('game_visible','Игра на экране','Game is visible','Гра на екрані'),('board_ready','Поле готово','Board ready','Поле готове'),('wait_board','Ожидаю игровое поле: закройте меню или окно','Waiting for the board: close menus or dialogs','Очікую ігрове поле: закрийте меню або вікно'),('wait_animation','Жду окончания анимации или возвращения к игре','Waiting for animation or return to game','Очікую завершення анімації або повернення до гри'),('wait_confirmation','Экран закрыт или ход ещё не подтверждён. Жду игру.','Screen obscured or move not confirmed. Waiting for the game.','Екран закрито або хід ще не підтверджено. Очікую гру.'),
('sprite_unknown','Не удалось уверенно определить удерживаемую фигуру','Could not confidently locate the held piece','Не вдалося впевнено визначити утримувану фігуру'),('sprite_verified','Положение фигуры проверено по кадру','Piece position verified on screen','Положення фігури перевірено за кадром'),('outside_screen','Поправка вышла за экран','Correction went outside the screen','Виправлення вийшло за екран'),('correction_failed','Положение не сошлось за три поправки','Position did not converge after three corrections','Положення не зійшлося за три виправлення'),('blind_release','Положение фигуры не проверено по кадру; отпускаю по расчётной точке','Could not verify the piece on screen; releasing at the planned point','Положення фігури не перевірено за кадром; відпускаю за розрахунковою точкою'),('correction_release','Точка отпускания скорректирована не полностью','Release point was only partially corrected','Точку відпускання скориговано не повністю'),
('error_generic','Ошибка устройства или распознавания. Проверьте телефон и журнал диагностики.','Device or recognition error. Check your phone and diagnostics.','Помилка пристрою або розпізнавання. Перевірте телефон і діагностику.'),('phone_unavailable','Телефон недоступен. Проверьте USB-подключение.','Phone unavailable. Check the USB connection.','Телефон недоступний. Перевірте USB-підключення.'),('profile_error','Не удалось прочитать профиль телефона.','Could not read the phone profile.','Не вдалося прочитати профіль телефона.'),
('auto_pace','Автоматический темп · лимит ходов: {limit}','Automatic speed · move limit: {limit}','Автоматичний темп · ліміт ходів: {limit}'),('ocr_unavailable','Распознавание очков недоступно: нужен Tesseract 5+ с языковой моделью.','Score recognition unavailable: Tesseract 5+ and a language model are required.','Розпізнавання балів недоступне: потрібен Tesseract 5+ з мовною моделлю.'),('capture_started','Видеопоток: {width} px · до {fps} кадров/с','Video stream: {width} px · up to {fps} fps','Відеопотік: {width} px · до {fps} кадрів/с'),('retry_pause','Несколько жестов не подтверждены. Бот приостановлен.','Several gestures unconfirmed. Bot paused.','Кілька жестів не підтверджено. Бота призупинено.'),('check_pause','Ходы доступны, но жесты не приняты. Проверьте экран и нажмите «Продолжить».','Legal moves exist but gestures were rejected. Check the screen and press Resume.','Ходи доступні, але жести не прийнято. Перевірте екран і натисніть «Продовжити».'),('retry_other','Жест не принят, проверяю другое размещение.','Gesture rejected, checking another placement.','Жест не прийнято, перевіряю інше розміщення.'),('retry_adjust','Повторяю ход с поправкой точки отпускания.','Retrying with an adjusted release point.','Повторюю хід із виправленою точкою відпускання.'),('gesture_cancelled','Жест отменён: {reason}','Gesture cancelled: {reason}','Жест скасовано: {reason}'),('game_mismatch','Результат жеста не совпал с моделью. Бот остановлен.','Gesture result differs from prediction. Bot stopped.','Результат жесту не збігся з моделлю. Бота зупинено.'),
]
LANGUAGES={'ru':'Русский','en':'English','uk':'Українська'}
CATALOGS={lang:{row[0]:row[index+1] for row in ROWS} for index,lang in enumerate(LANGUAGES)}

def tr(key,lang='ru',**values):
    return CATALOGS.get(lang,CATALOGS['ru'])[key].format(**values)

REASONS={
'Жесты не подтверждены. Проверьте экран и запустите бота заново.':'retry_finished',
'Лоток остаётся пустым. Проверьте игру и запустите бота заново.':'empty_tray_finished',
'Обнаружена новая партия. Запустите бота заново.':'new_game_finished',
'Позиция изменилась во время паузы. Запустите бота заново.':'position_changed_finished',

'Нет доступных размещений после отклонённых жестов':'check_pause','Экран изменился или закрыт анимацией/окном. Проверьте телефон.':'screen_obscured','Поле 8×8 не найдено: откройте классическую игру или задайте board в профиле.':'board_not_found','Поле закрыто окном или анимацией':'screen_obscured','Некорректные границы поля':'profile_error','Область фигур за пределами экрана':'profile_error','Не удалось определить размер блоков':'recognition_error','Необычная фигура: проверьте профиль и скриншот':'recognition_error','Фигура не распознана':'recognition_error','Видеопоток закрыт':'stream_error','Нет новых кадров видеопотока; проверьте ADB.':'stream_error',
'Этот телефон уже управляется другим экземпляром BlockBlast BOT. Сначала остановите его.':'device_busy','ADB не ответил за 8 секунд':'adb_timeout','ADB не найден. Установите Android platform-tools.':'adb_missing','Разрешение экрана отличается от профиля. Выберите подходящий профиль.':'profile_resolution',
'Завершено':'finished','Нет доступных ходов':'no_moves','Достигнут лимит ходов':'limit_reached','Остановлено пользователем (Ctrl+C / кнопка Стоп)':'user_stop','Пауза по кнопке':'manual_pause','Экран заблокирован или выключен':'screen_locked','Открыта шторка уведомлений':'shade_open','Ожидаю возвращения в Block Blast':'wait_game','Block Blast на экране':'game_visible','Игра на экране':'game_visible','Поле готово':'board_ready','Ожидаю игровое поле: закройте меню или окно':'wait_board','Жду окончания анимации или возвращения к игре':'wait_animation','Экран закрыт или ход ещё не подтверждён. Жду игру.':'wait_confirmation','Подключаю телефон':'connecting',
'Не удалось уверенно определить удерживаемую фигуру':'sprite_unknown','Положение фигуры проверено по кадру':'sprite_verified','Поправка вышла за экран':'outside_screen','Положение не сошлось за три поправки':'correction_failed','Положение не проверено, отпускаю по расчётной точке':'blind_release','Точка отпускания скорректирована не полностью':'correction_release','Результат жеста не совпал с моделью. Бот остановлен.':'game_mismatch',
}

def reason(text,lang='ru'):
    if not text:return tr('ready',lang)
    if text in REASONS:return tr(REASONS[text],lang)
    if text.startswith('Телефон недоступен:'):return tr('phone_unavailable',lang)
    if text.startswith('Ошибка: '):return reason(text[8:],lang)
    if text.startswith('Не дождался стабильного игрового экрана:'):return tr('screen_obscured',lang)
    if text.startswith('Видеопоток не выдаёт кадры:'):return tr('stream_error',lang)
    # External exception text is retained in raw diagnostic files, never leaked as UI identifiers.
    return tr('error_generic',lang)

DEBUG_EVENTS={'timing'}
VISIBLE_EVENTS={'storage_warning','start','attempt','move','motion','summary','rejected','paused','resumed','resync_after_pause','tray_resync','unstable_screen','capture_fallback','error','timing','board_resync'}

def event_text(event,lang='ru'):
    kind=event.get('event');data=dict(event)
    data.update(slot=event.get('slot',0)+1,row=event.get('row',0)+1,col=event.get('col',0)+1,score=event.get('score') if event.get('score') is not None else '—',move=event.get('move','?'),attempt=event.get('attempt','?'),lines=event.get('lines',0))
    if kind in ('move','attempt'):return tr(kind+'_text',lang,**data)
    if kind=='start':return tr('start_text',lang)
    if kind=='storage_warning':return tr('storage_warning',lang)
    if kind in ('summary','paused'):return tr(kind+'_text',lang,reason=reason(event.get('reason',''),lang))
    if kind=='resumed':
        from .history import duration
        return tr('resumed_text',lang,duration=duration(event.get('seconds')))
    if kind=='rejected':return tr('rejected_text',lang,attempt=data['attempt'])
    if kind=='motion':return tr('motion_text',lang,reason=reason(event.get('reason',''),lang),count=event.get('corrections',0))
    if kind=='timing':
        if event.get('stage')=='cycle':
            return tr('timing_cycle_text',lang,read=event.get('read',0),plan=event.get('plan',0),
                      gesture=event.get('gesture',0),verify=event.get('verify',0))
        return tr('timing_text',lang,seconds=event.get('seconds',0))
    if kind=='error':return reason(event.get('message',''),lang)
    key={'board_resync':'board_resync','resync_after_pause':'resync','tray_resync':'tray_resync','unstable_screen':'unstable','capture_fallback':'capture_fallback'}.get(kind)
    if key:return tr(key,lang)
    if kind=='message':
        values=dict(event.get('params',{}))
        if 'reason' in values:values['reason']=reason(values['reason'],lang)
        if values.get('limit')==0:values['limit']=tr('unlimited',lang)
        return tr(event['key'],lang,**values)
    return ''

def event_type(event):
    kind=event.get('event')
    if kind=='message':kind=event.get('key')
    if kind in ('move','attempt'):return kind
    if kind in ('paused','resumed','retry_pause','check_pause'):return 'pause'
    if kind in ('error','gesture_cancelled'):return 'error'
    if kind in ('rejected','retry_other','retry_adjust'):return 'rejected'
    if kind=='timing':return 'debug'
    return 'info'

def legacy_action(text):
    """Normalize old ten-entry summaries, which predate structured timelines."""
    import re
    match=re.search(r'(Ход (\d+)|Отклонено): Фигура (\d+) → строка (\d+), столбец (\d+); линий (\d+)',text)
    if match:
        return dict(event='rejected' if match[1]=='Отклонено' else 'move',move=int(match[2] or 0),attempt='?',slot=int(match[3])-1,row=int(match[4])-1,col=int(match[5])-1,lines=int(match[6]))
    return dict(event='message',key='archive_old',params={})
