import pandas as pd
import yfinance as yf
from gdeltdoc import Filters, GdeltDoc


def get_data_yfinance(quotation: str, start_date: str, end_date: str, interval='1d') -> pd.DataFrame:
    """
    Взять данные с yahoo finance

    params:
        quotation: название котировки, данные для которой хотим получить
        start_date, end_date - интервал, формат "год-месяц-день"
        interval - периодичность, формат "(номер)(первая буква слова (d, m, y))"
    returns:
        DataFrame формата "Тикет, Время, 6 видов цен"
    """

    df_res = yf.download(tickers=quotation,
                         start=start_date,
                         end=end_date,
                         interval=interval)
    df_res.loc[:, 'Ticker'] = quotation
    df_res = df_res.groupby(pd.Grouper(level="Date", freq=interval.upper())).mean()
    # Приводим время к одному виду для слияния
    df_res.index = pd.to_datetime(df_res.index).tz_localize('Etc/UCT')
    return df_res


def get_data_gdelt(quotation: str, keywords: list, start_date: str, end_date: str, interval="1d", num_records=250,
                   repeats=3) -> pd.DataFrame:
    """
    Взять данные с gdelt

    params:
        quotation - имя ценной бумаги
        keywords - из графа знаний по ключевому слову
        start_date, end_date - интервал, формат "год-месяц-день"
        (опционально) interval - периодичность, формат "(номер)(первая буква слова (d, m, y))"
        (не реализована) (опционально) num_records - сколько максимум записей взять за промежуток
        (не реализовано) (опционально) repeats - сколько раз должно повториться ключевое слово в статье
    returns:
        DataFrame формата "Datetime (индекс), Ticker,
        [Average_Tone, Article_Count, Volume_Intensity]_[std, mean, sum, min, max]
    """

    df_res = None
    df_dub = pd.DataFrame()
    # Как называются колонки в полученных DataFrames
    col_names = ['Average_Tone', 'Article_Count', 'Volume_Intensity']

    # Что будем искать для данных ключевых слов
    # Тон статей, их количество и их кол-во в отношении ко всем остальным
    match_list = ["timelinetone", "timelinevolraw", "timelinevol"]
    match_dict = dict(zip(match_list, col_names))
    for ft in keywords:
        try:
            f = Filters(
                start_date=start_date,
                end_date=end_date,
                keyword=ft
            )

            for timeline in match_list:
                gd = GdeltDoc()
                timeline_data = gd.timeline_search(timeline, f)
                import time
                time.sleep(5)
                timeline_data = timeline_data.fillna(0)
                timeline_data = timeline_data.groupby(pd.Grouper(key="datetime", freq=interval.upper()))

                if timeline in ['timelinetone']:
                    timeline_data = timeline_data.mean()
                else:
                    timeline_data = timeline_data.sum()

                # Собираем все фичи в один датафрейм, далее их разделим
                col_name = match_dict[timeline]
                df_dub[f"{ft}_{timeline}_{col_name}"] = timeline_data[col_name.replace('_', ' ')].values

                # Так как мы копируем только колонки, то надо один раз откопировать дату в итог
                if df_res is None:
                    # Так же выровняем индексы, чтобы при копировании не выдавалось NaN
                    df_res = pd.DataFrame(index=timeline_data.index)
                    df_dub.index = timeline_data.index

            print('TICKER:', quotation, 'KEY:', ft)
        except Exception as e:
            print('ERROR!', e, 'TICKER:', quotation, 'KEY:', ft)
    # Нужно создать колонки со средним, средним отклонением, минимумом и максимумом для каждой фичи
    # Сначала сформируем список датафреймов, которые нам нужно достать для каждой колонки
    for pattern in col_names:
        pattern_list = list()
        for col in df_dub.columns:
            if pattern in col:
                pattern_list.append(col)

        # Теперь для pattern у нас есть список
        # Посчитаем для неё std, mean, min, max, sum
        df_res[f'{pattern}_min'] = df_dub[pattern_list].min(axis=1, skipna=True)
        df_res[f'{pattern}_max'] = df_dub[pattern_list].max(axis=1, skipna=True)
        df_res[f'{pattern}_mean'] = df_dub[pattern_list].mean(axis=1, skipna=True)
        df_res[f'{pattern}_std'] = df_dub[pattern_list].std(axis=1, skipna=True)
        df_res[f'{pattern}_sum'] = df_dub[pattern_list].sum(axis=1, skipna=True)

    # Добавим название ценной бумаги в таблицу
    df_res.loc[:, 'Ticker'] = quotation
    return df_res


def get_dataframe(**kwargs) -> pd.DataFrame:
    """
    Получить полный датафрейм с источников
    Пример использования: d = get_dataframe(quotation='NVDA',
                                            keywords=['nvidia', 'geforce', 'geforce rtx', 'geForce now',
                                            'nvidia rtx', 'nvidia shield', 'nvidia dgx'],
                                            start_date="2020-01-01",
                                            end_date="2020-12-31")

    params:
        quotation - имя ценной бумаги
        keywords - из графа знаний по ключевому слову
        start_date, end_date - интервал, формат "год-месяц-день"
        (опционально) interval - периодичность, формат "(номер)(первая буква слова (d, m, y))"
        (не реализована) (опционально) num_records - сколько максимум записей взять за промежуток
        (не реализовано) (опционально) repeats - сколько раз должно повториться ключевое слово в статье
    returns:
        DataFrame формата "Datetime (индекс), Ticker,
        [Average_Tone, Article_Count, Volume_Intensity]_[std, mean, sum, min, max], - из новостей
        Open, High, Low, Close, Adj Close, Volume - из финансов
    """

    gdelt_data = get_data_gdelt(**kwargs)
    yfinance_data = get_data_yfinance(quotation=kwargs['quotation'],
                                      start_date=kwargs['start_date'],
                                      end_date=kwargs['end_date'],
                                      interval="1d" if not kwargs.get('interval') else kwargs['interval'])

    res = pd.concat([gdelt_data, yfinance_data], axis=1)

    del gdelt_data
    del yfinance_data

    return res
