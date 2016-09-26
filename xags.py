'''
每股现金流 用去年年报
'''
import pandas as pd
import time
from datetime import date
from datetime import timedelta
import tradestat
'''
================================================================================
总体回测前
================================================================================
'''
#总体回测前要做的事情
def initialize(context):
    set_params()                             # 设置策略常量
    set_variables()                          # 设置中间变量
    set_backtest()                           # 设置回测条件
    # 加载统计模块
    if g.flag_stat:
        g.trade_stat = tradestat.trade_stat()
    f = 12  # 调仓频率
    g.Transfer_date = range(1,13,12/f)
    run_monthly(Transfer,20)

#1 
#设置策略参数
def set_params():
    g.num_stocks = 5                             # 每次调仓选取的最大股票数量
    g.stocks=get_all_securities(['stock']).index # 设置上市A股为初始股票池 000002.XSHG
    
    g.per_year = 0.25                            # EPS增长率不低于0.25
    g.per_quarter = 0.25                         # EPS增长率不低于0.25
    g.flag_stat = False                          # 默认不开启统计
    g.trade_skill = False                        # 开启交易策略
    g.yearVS = 4+1                               # 比较3年的EPS，去年年报不一定出
    g.quarterVS = 3                              # 比较3季度的EPS

#2
#设置中间变量
def set_variables():
    return None

#3
#设置回测条件
def set_backtest():
    set_option('use_real_price',True)        # 用真实价格交易
    log.set_level('order','debug')           # 设置报错等级

'''
================================================================================
每天开盘前
================================================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    set_slip_fee(context)                 # 设置手续费与手续费
    # 设置可行股票池
    
#4
# 设置可行股票池：过滤掉当日停牌的股票
# 输入：initial_stocks为list类型,表示初始股票池； context（见API）
# 输出：unsuspened_stocks为list类型，表示当日未停牌的股票池，即：可行股票池
def set_feasible_stocks(initial_stocks,context):
    # 判断初始股票池的股票是否停牌，返回list
    unsuspened_stocks =filter_paused_stock(initial_stocks)    
    unsuspened_stocks = filter_st_stock(unsuspened_stocks)
    return unsuspened_stocks

# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]
    
# 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list 
        if not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name 
        and '*' not in current_data[stock].name 
        and '退' not in current_data[stock].name]

#5
# 根据不同的时间段设置滑点与手续费
# 输入：context（见API）
# 输出：none
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
        
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
            
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))


'''
================================================================================
每天交易时
================================================================================
'''
'''
# 每天回测时做的事情
def handle_data(context,data):
    # 需买入的股票
    list_to_buy = pick_buy_list(context, data, g.feasible_stocks)
    # 待卖出的股票，list类型
    list_to_sell = stocks_to_sell(context, data, list_to_buy)
    # 卖出操作
    sell_operation(context,list_to_sell)
    # 买入操作
    buy_operation(context, list_to_buy)
'''
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def Transfer(context):
    months = context.current_dt.month
    if months in g.Transfer_date:
        g.feasible_stocks = set_feasible_stocks(g.stocks,context)
        g.feasible_stocks = stocks_can_buy(context)
        log.debug(g.feasible_stocks)
        # 待卖出的股票，list类型
        list_to_sell = stocks_to_sell(context, g.feasible_stocks)
        # 需买入的股票
        list_to_buy = pick_buy_list(context, g.feasible_stocks, list_to_sell)
        # 卖出操作
        sell_operation(context,list_to_sell)
        # 买入操作
        buy_operation(context, list_to_buy)
    
#6
# 计算股票的PEG值
# 输入：context(见API)；stock_list为list类型，表示股票池
# 输出：df_PEG为dataframe: index为股票代码，data为相应的PEG值
def get_PEG(context, stock_list): 
    # 查询股票池里股票的市盈率，收益增长率
    q_PE_G = query(valuation.code, valuation.pe_ratio, indicator.inc_operation_profit_year_on_year
                 ).filter(valuation.code.in_(stock_list)) 
    # 得到一个dataframe：包含股票代码、市盈率PE、收益增长率G
    # 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
    df_PE_G = get_fundamentals(q_PE_G)
    # 筛选出成长股：删除市盈率或收益增长率为负值的股票
    df_Growth_PE_G = df_PE_G[(df_PE_G.pe_ratio >0)&(df_PE_G.inc_operation_profit_year_on_year >0)]
    # 去除PE或G值为非数字的股票所在行
    df_Growth_PE_G.dropna()
    # 得到一个Series：存放股票的市盈率TTM，即PE值
    Series_PE = df_Growth_PE_G.ix[:,'pe_ratio']
    # 得到一个Series：存放股票的收益增长率，即G值
    Series_G = df_Growth_PE_G.ix[:,'inc_operation_profit_year_on_year']
    # 得到一个Series：存放股票的PEG值
    Series_PEG = Series_PE/Series_G
    # 将股票与其PEG值对应
    Series_PEG.index = df_Growth_PE_G.ix[:,0]
    # 将Series类型转换成dataframe类型
    df_PEG = pd.DataFrame(Series_PEG)
    return df_PEG
    
# 挑选净利润同比增长率连续3年大于0.25的
# 输入：context(见API)；stock_list为list类型，表示初始股票池
# 输出：buy_list_stocks为list: 为股票代码
def get_growth_stock(context, stock_list): 
    pe_ration_max = 40
    # 查询股票池里股票的市盈率，收益增长率 indicator.inc_operation_profit_year_on_year
    q_PE_G = query(valuation.code, valuation.pe_ratio, indicator.inc_operation_profit_year_on_year
                 ).filter(valuation.code.in_(stock_list)) 
    # 得到一个dataframe：包含股票代码、市盈率PE、收益增长率G
    # 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
    df_PE_G = get_fundamentals(q_PE_G)
    # 筛选出成长股：删除市盈率或收益增长率为负值的股票
    df_Growth_PE_G = df_PE_G[(df_PE_G.pe_ratio>0)&(df_PE_G.pe_ratio<pe_ration_max)&(df_PE_G.inc_operation_profit_year_on_year >20)]
    # 去除PE或G值为非数字的股票所在行
    df_Growth_PE_G.dropna()

    list_stock = list(df_Growth_PE_G.loc[:,'code'])
    #K70 	房地产业    J66 货币金融服务
    list_fdc = get_industry_stocks('K70')
    list_hbjr = get_industry_stocks('J66')
    
    # 去掉房地产
    for i in list_fdc:
        if i in list_stock:
            list_stock.remove(i)
    # 去掉超大盘 000043.XSHG 399980.XSHE
    cdp = get_index_stocks('000043.XSHG')
    for i in cdp:
        if i in list_stock:
            list_stock.remove(i)
    cdp = get_index_stocks('399980.XSHE')
    for i in cdp:
        if i in list_stock:
            list_stock.remove(i)
    
    q_PE_G2 = query(valuation.code, valuation.capitalization, cash_flow.pubDate,\
                valuation.pe_ratio, income.basic_eps, balance.statDate
                 ).filter(valuation.code.in_(list_stock)
                 )

    buy_list_stocks = []
    # 查询股票池里股票的EPS,股本(万股),发布财报日期,eps,
    # 经营活动现金流入(元),经营活动现金流出(元)
    # 净利润同比增长率 ==> 每股现金流
    # 处理过去3年的数据
    # 每股现金流 > eps_year(去年)*1.2
    
    year = context.current_dt.year
    month = context.current_dt.month
    # 读取前8个季度报表
    quarterList = [([]) for i in range(9)]
    yearW = year
    if month > 9:
        quarterLast = 3
    elif month > 6:
        quarterLast = 2
    elif month > 3:
        quarterLast = 1
    else:
        quarterLast = 4
        yearW -= 1
        
    for i in range(9):
        if quarterLast-i<=0:     #本年前i个季度
            quarterLast += 4
            yearW -= 1
        quarterList[i] = str(yearW)+'q'+str(quarterLast-i)
        
    log.debug(quarterList)
    
    yearP1 = get_fundamentals(q_PE_G2, statDate=str(year-1))
    yearL = [year-g.yearVS+i for i in range(g.yearVS)]  # 2011 2012 2013 2014 2015 今年2016
    
    yearP = [get_fundamentals(q_PE_G2, statDate=str(yearL[i])) for i in range(g.yearVS)]
    quarterP = [get_fundamentals(q_PE_G2, statDate=str(quarterList[i])) \
                for i in range(9)]               # 前8季度
    q_jbm = query(valuation.code, valuation.pe_ratio, \
            cash_flow.subtotal_operate_cash_inflow, \
            cash_flow.subtotal_operate_cash_outflow, \
            balance.total_liability, balance.total_sheet_owner_equities
            ).filter(valuation.code.in_(list_stock))
    jbmP = [get_fundamentals(q_jbm, statDate=str(yearL[i+3])) for i in range(2)]
    q_now = query(valuation.code, valuation.capitalization, valuation.pe_ratio,\
                balance.statDate, balance.pubDate)
    df_now = get_fundamentals(q_now)

    
    for i in list_stock:
        # 流通市值>500跳过
        #if .loc[0,'circulating_market_cap'] > 500:
        #    continue
        #log.info(yearP1)

        start_yearth = 1
        # 2016-08-29 2016-04-04
        # datanow = time.strptime(, "%Y-%m-%d")
        # datapub = time.strptime(, "%Y-%m-%d")
        if yearP1[yearP1.code==i].empty:
            start_yearth = 0
        elif context.current_dt.strftime("%Y-%m-%d") < yearP1[yearP1.code==i]['pubDate'].values[0]:
            start_yearth = 0
            #log.debug('未公布')
        #log.debug('%s %s 年报%s %d',i, datanow, datapub, year-1-start_yearth)

        # 回测当天，前4年的已出的年报有无空的    
        flag_empty = False
        for j in range(start_yearth, 4+start_yearth):
            if yearP[j][yearP[j].code==i].empty:
                flag_empty = True
                break
        if flag_empty:
            continue
            
        start_quarterth = 1
        #2014-12-31
        if df_now[df_now.code==i]['statDate'].values[0][6] == '3':
            qlast = 1
        elif df_now[df_now.code==i]['statDate'].values[0][6] == '6':
            qlast = 2
        elif df_now[df_now.code==i]['statDate'].values[0][6] == '9':
            qlast = 3
        elif df_now[df_now.code==i]['statDate'].values[0][6] == '2':
            qlast = 4
            
        
        if qlast == int(quarterList[0][-1]):
            #上季度的季报已公开； 0为上季度季报
            start_quarterth = 0
        
        #log.debug(i, qlast, quarterList[0][-1], df_now[df_now.code==i]['statDate'].values[0], df_now[df_now.code==i]['pubDate'].values[0], start_quarterth)
        
        eps_year = [1]*(g.yearVS-1)      # 2011 2012 2013 2014 or 2012 ... 今年2016
        cap_year = [1]*(g.yearVS-1)           # 2011 2012 2013 2014 or 2012 ... 今年2016
        for j in range(g.yearVS-1):
            eps_year[j] = yearP[j+start_yearth][yearP[j+start_yearth].code==i]['basic_eps'].values[0]
            cap_year[j] = yearP[j+start_yearth][yearP[j+start_yearth].code==i]['capitalization'].values[0]
        
        if eps_year[0]<0:
            continue
        
        # 季报
        eps_q = [1]*g.quarterVS
        eps_q_lastyear = [1]*g.quarterVS
        cap_q = [1]*g.quarterVS
        cap_q_lastyear = [1]*g.quarterVS
        for j in range(g.quarterVS): 
            qThis = quarterP[j+start_quarterth][quarterP[j+start_quarterth].code==i]
            qThis_n = quarterP[j+start_quarterth+1][quarterP[j+start_quarterth+1].code==i]
            qThis_lyear = quarterP[j+start_quarterth+4][quarterP[j+start_quarterth+4].code==i]
            qThis_l_n = quarterP[j+start_quarterth+5][quarterP[j+start_quarterth+5].code==i]
            eps_q[j] = qThis['basic_eps'].values[0]
            cap_q[j] = qThis['capitalization'].values[0]
            eps_q_lastyear[j] = qThis_lyear['basic_eps'].values[0]
            cap_q_lastyear[j] = qThis_lyear['capitalization'].values[0]

        cap_now = df_now[df_now.code==i]['capitalization'].values[0]

        df_lastyear = jbmP[start_yearth][jbmP[start_yearth].code==i]
        df_lastyear2 = yearP[3+start_yearth][yearP[3+start_yearth].code==i]

        flag_cz = True        
        for j in range(g.yearVS-2):      # 2011 2012 2013 2014 or 2012 ... 今年2016
            if (1+g.per_year)*eps_year[j]*cap_year[j] > eps_year[j+1]*cap_year[j+1]:
                # 增长不达 (1+per)上年 > 今年
                flag_cz = False
                break
        for j in range(g.quarterVS):
            if (1+g.per_quarter)*(eps_q_lastyear[j]*cap_q_lastyear[j]) > (eps_q[j]*cap_q[j]):
                # 增长不达 (1+per)上年这季 > 这季
                flag_cz = False
                break
        # todo
        if flag_cz:
            
            log.debug('%s y=%.2f 1y=%.2f 2y=%.2f 3y=%.2f', i, eps_year[3], eps_year[2], eps_year[1], eps_year[0])
            log.debug('%s now  0=%.2f 1q=%.2f 2q=%.2f', i, eps_q[0], eps_q[1], eps_q[2])
            log.debug('%s now  0=%d 1q=%d 2q=%d', i, cap_q[0], cap_q[1], cap_q[2])
            log.debug('%s last 0=%.2f 1q=%.2f 2q=%.2f', i, eps_q_lastyear[0], eps_q_lastyear[1], eps_q_lastyear[2])
            log.debug('%s last 0=%d 1q=%d 2q=%d', i, cap_q_lastyear[0], cap_q_lastyear[1], cap_q_lastyear[2])
            #log.debug('%i 0=%.2f 1=%.2f 2=%.2f 3=%.2f', start_yearth, cap_year[0], cap_year[1], cap_year[2], cap_year[3])
            #log.info("code=%s, market_cap=%d", i, yearP1[0, 'circulating_market_cap'])

            #每股现金流 > eps_year(去年) *1.2 mgxjl
            if df_lastyear['subtotal_operate_cash_inflow'].values[0] - df_lastyear['subtotal_operate_cash_outflow'].values[0] > df_lastyear2['basic_eps'].values[0]*df_lastyear2['capitalization'].values[0]*10000 * 1.2:
                buy_list_stocks.append(i)
            # 动态市盈率 负债合计(元)/负债和股东权益合计
            
            #满分 1+1+1
            # scoreOfStock = 0
            # pe_ratio 动态市盈率  负债合计(元)/负债和股东权益合计= 资产负债率 < 0.5
            # zcfzl = df_lastyear['total_liability'].values[0]/df_lastyear['total_sheet_owner_equities'].values[0]
            '''
            if df_lastyear['pe_ratio'].values[0] <= pe_ration_max:
                if zcfzl<0.5:
                    scoreOfStock = scoreOfStock + 1
                #每股现金流 > eps_year(去年)
                if df_lastyear['subtotal_operate_cash_inflow'].values[0] - df_lastyear['subtotal_operate_cash_outflow'].values[0] > df_lastyear2['basic_eps'].values[0]*df_lastyear2['capitalization'].values[0]*10000:
                    scoreOfStock = scoreOfStock + 1
            '''

            #log.info("code=%s, eps_year=%f, yearL1 = %d, mgxjl=%.2f", i,   eps_year[3],year-5+start_yearth, (df_lastyear['subtotal_operate_cash_inflow'].values[0] - df_lastyear['subtotal_operate_cash_outflow'].values[0])/df_lastyear2['capitalization'].values[0]/10000)
    #log.debug(buy_list_stocks)            

    return buy_list_stocks
    
#7
# 获得买入信号
# 输入：context(见API)
# 输出：list_to_buy为list类型,表示待买入的g.num_stocks支股票
def stocks_can_buy(context):
    list_can_buy = []
    # 得到一个dataframe：index为股票代码，data为相应的PEG值
    list_pick = get_growth_stock(context, g.feasible_stocks)
    # 将股票按PEG升序排列，返回daraframe类型
    # df_sort_PEG = df_PEG.sort(columns=[0], ascending=[1])
    # 将存储有序股票代码index转换成list并取前g.num_stocks个为待买入的股票，返回list

    #nummax = min(len(df_PEG.index), g.num_stocks-len(context.portfolio.positions.keys()))
        
    for i in list_pick:
        list_can_buy.append(i)
    #log.debug(list_can_buy)
    return list_can_buy
    
    
 
'''
================================================================================
多均线策略
================================================================================
'''
# 判断均线纠缠
def is_struggle(mavg1,mavg2,mavg3):
    if abs((mavg1-mavg2)/mavg2)< 0.003\
    or abs((mavg2-mavg3)/mavg3)< 0.002:
        return True
    return False
    
# 计算股票过去n个单位时间（一天）均值
# n 天的MA， day_before天前
def count_ma(stock,n, day_before):
    #log.debug(history(n, '1d', 'close', [stock])[stock])
    #log.debug(history(n, '1d', 'close', [stock],df = False)[stock].mean())
    return history(n+day_before, '1d', 'close', [stock],df = False)[stock][0:n].mean()


# 判断多头排列 5 10 20 30
def is_highest_point(stock,n):
    if count_ma(stock,5,n) > count_ma(stock,10,n)\
    and count_ma(stock,10,n) > count_ma(stock,20,n)\
    and count_ma(stock,20,n) > count_ma(stock,30,n):
        #log.debug('%s, ma5=%.2f, ma10=%.2f, ma20=%.2f, ma30=%.2f', stock, count_ma(stock,5,-n)\
        #,count_ma(stock,10,-n),count_ma(stock,20,-n),count_ma(stock,30,-n))
        return True
    return False

# 判断空头排列——空仓 5 10 20
def is_lowest_point(stock,n):
    if count_ma(stock,5,n) < count_ma(stock,10,n)\
    and count_ma(stock,10,n) < count_ma(stock,20,n):
        log.debug('%d, %s, ma5=%.2f, ma10=%.2f, ma20=%.2f',n, stock, count_ma(stock,5,n), count_ma(stock,10,n), count_ma(stock,20,n))
        return True
    return False
    
    
# 判断10日线， 20日线空头排列后的金叉——买入
def is_crossUP(stock,short,long):
    if is_lowest_point(stock,1) and is_lowest_point(stock,2):
        if count_ma(stock, short, 1) < count_ma(stock, long, 1)\
        and count_ma(stock, short, 0) > count_ma(stock, long, 0):
            return True
    return False

# 判断多头排列后的死叉——卖出
def is_crossDOWN(stock,short,long):
    if is_highest_point(stock,1) and is_highest_point(stock,2):
        if count_ma(stock, short, 1) > count_ma(stock, long, 1)\
        and count_ma(stock, short, 0) < count_ma(stock, long, 0):
            log.debug('%s, MAs-2:%.2f, MAl-2:%.2f; MAs-1:%.2f MAl-1:%.2f', stock, count_ma(stock, short, 1), count_ma(stock, long, 1), count_ma(stock, short, 0), count_ma(stock, long, 0))
            return True
    return False
'''
================================================================================
多均线策略
================================================================================
''' 
# 获得买入的list_to_buy
# 输入list_can_buy 为list，可以买的队列
# 输出list_to_buy 为list，买入的队列
def pick_buy_list(context, list_can_buy, list_to_sell):
    list_to_buy = []
    buy_num = g.num_stocks - len(context.portfolio.positions.keys()) + len(list_to_sell)
    if buy_num <= 0:
        return list_to_buy
    # 得到一个dataframe：index为股票代码，data为相应的PEG值
    ad_num = 0;
    if g.trade_skill:
        for stock in list_can_buy:
            if stock in context.portfolio.positions.keys():
                continue
            ma20 = count_ma(stock, 20, 0)
            close2day = history(2, '1d', 'close', [stock],df = False)[stock]
            if is_struggle(close2day[-2],close2day[-1],ma20):
                continue
            if close2day[-2] < ma20 and close2day[-1] > ma20:
                list_to_buy.append(stock)
                ad_num += 1
                if ad_num >= buy_num:
                    break
                
            '''
            if stock not in context.portfolio.positions.keys():
                list_to_buy.append(stock)
            # MA60上才考虑买
            ma60 = count_ma(stock, 60, 0)
            if close < ma60:
                continue
            '''
            
            '''
            # 多头排列——满仓买入
            if is_highest_point(data,stock,0):
                # 均线纠缠时，不进行买入操作
                if is_struggle(count_ma(stock,10,0),count_ma(stock,20,0),count_ma(stock,30,0)):
                    continue
                else:
                    if close < ma20:
                        list_to_buy.append(stock)
                        ad_num += 1
                        if ad_num >= buy_num:
                            break
                        continue
            # 空头排列后金叉——满仓买入 10, 20 金叉
            if is_crossUP(data,stock,10, 20):
                if is_struggle(count_ma(stock,10,0), \
                    count_ma(stock,20,0),count_ma(stock,30,0)):
                    continue
                list_to_buy.append(stock)
                ad_num += 1
                if ad_num >= buy_num:
                    break
            '''
    else:
        for stock in list_can_buy:
            if stock in context.portfolio.positions.keys():
                continue
            list_to_buy.append(stock)
            ad_num += 1
            if ad_num >= buy_num:
                break
            
    return list_to_buy

# 已不再具有持有优势的股票
# 输入：context(见API)；stock_list_now为list类型，表示初始持有股, stock_list_buy为list类型，表示可以买入的股票
# 输出：应清仓的股票 list
def get_clear_stock(context, stock_list_buy):
    # 

    stock_hold = []
    year = context.current_dt.year
    stock_list_now = context.portfolio.positions.keys()
    for i in stock_list_now:
        q_PE_G = query(valuation.capitalization, income.basic_eps, cash_flow.pubDate
                 ).filter(valuation.code == i)

        jbm = get_fundamentals(q_PE_G, statDate=str(year-1))
        jbmP2 = get_fundamentals(q_PE_G, statDate=str(year-2))
        if context.current_dt.strftime("%Y-%m-%d") <= jbm.loc[0,'pubDate']:
            jbm = get_fundamentals(q_PE_G, statDate=str(year-2))
            jbmP2 = get_fundamentals(q_PE_G, statDate=str(year-3))
        #log.info(jbm)
        #log.info(jbmP2)
        if jbm.loc[0, 'basic_eps']*jbm.loc[0, 'capitalization'] >= (1+g.per)*jbmP2.loc[0, 'basic_eps']*jbmP2.loc[0, 'capitalization']:
            stock_hold.append(i)
        else:
            log.info("code=%s, jbm=%f, jbmP2=%f", i, jbm.loc[0, 'basic_eps']*jbm.loc[0, 'capitalization'], jbmP2.loc[0, 'basic_eps']*jbmP2.loc[0, 'capitalization'])
        #log.info("code=%s, jbm=%f, jbmP2=%f", i, jbm.loc[0, 'basic_eps']*jbm.loc[0, 'capitalization'], (1+g.per)*jbmP2.loc[0, 'basic_eps']*jbmP2.loc[0, 'capitalization'])

    list_to_sell = []
    #log.info(stock_hold)
    stock_can_buy = stock_hold      # +stock_list_buy
    for i in stock_list_buy:
        stock_can_buy.append(i)
    #log.info(stock_can_buy)
    #全都不值的保留
    if stock_can_buy is None:
        return stock_list_now
    news_ids = []
    for id in stock_can_buy:
        if id not in news_ids:
            news_ids.append(id)
    #log.debug(news_ids, "stock_can_buy")
    
    
    # 得到一个dataframe：index为股票代码，data为相应的PEG值
    df_PEG = get_PEG(context, news_ids)
    # 将股票按PEG升序排列，返回daraframe类型
    df_sort_PEG = df_PEG.sort(columns=[0], ascending=[1])
    # 将存储有序股票代码index转换成list并取前g.num_stocks个为待买入的股票，返回list
    nummax = min(len(df_PEG.index), g.num_stocks)
    stock_hold = list(df_sort_PEG[0:g.num_stocks].index)
    # 如果持有不应持有的股票卖出
    for i in stock_list_now:
        if i not in stock_hold:
            list_to_sell.append(i)
    
    # 得到一个dataframe：index为股票代码，data为相应的PEG值
    df_PEG = get_PEG(context, stock_list_now)
    # 将股票按PEG升序排列，返回daraframe类型
    df_sort_PEG = df_PEG.sort(columns=[0], ascending=[1])

    len_df = len(df_PEG.index)
    for i in range(len_df):
        if df_sort_PEG.ix[i,0] > 1.2:
            list_to_sell.append(df_sort_PEG.index[i])
            #log.info("code=%s PEG>1.2", i)
            
    return list_to_sell
# 获得均线卖出信号
# 输入：context（见API文档）
# 输出：list_to_sell为list类型，表示待卖出的股票
def stocks_djx_to_sell(context):
    list_to_sell = []
    list_hold = context.portfolio.positions.keys()
    if len(list_hold) == 0:
        return list_to_sell
    
    for i in list_hold:
        '''
        close = history(1, '1d', 'close', [i],df = False)[i][0]
        # 跌到MA60卖
        ma60 = count_ma(i, 60, 0)
        if close < ma60:
            list_to_sell.append(i)
            continue
        '''
        # 均线纠缠时，不进行操作
        if is_struggle(count_ma(i,5,1),count_ma(i,10,1),count_ma(i,20,1)):
            continue
        # 空头排列——清仓卖出
        if is_lowest_point(i,-1):
            list_to_sell.append(i)
        # 多头排列后死叉——清仓卖出 10 叉 20
        elif is_crossDOWN(i,10,20):
            list_to_sell.append(i)
        hist = attribute_history(i, t, '1d', 'close', df=False)
        if context.portfolio.positions[i].avg_cost *0.95 >= hist['close'][0]:
            #亏损 5% 卖出
            list_to_sell.append(i)
        '''
        if context.portfolio.positions[i].avg_cost *1.15 <= data[i].close:
            #赚 10% 卖出
            list_to_sell.append(i)
        '''
    return list_to_sell
    
# 获得均线卖出信号
# 输入：context（见API文档）
# 输出：list_to_sell为list类型，表示待卖出的股票
def stocks_udma_to_sell(context):
    list_to_sell = []
    list_hold = context.portfolio.positions.keys()
    if len(list_hold) == 0:
        return list_to_sell
    for stock in list_hold:
        ma20 = count_ma(stock, 20, 0)
        close2day = history(2, '1d', 'close', [stock],df = False)[stock]
        if is_struggle(close2day[-2],close2day[-1],ma20):
            continue
        if close2day[-2] > ma20 and close2day[-1] < ma20:
            list_to_sell.append(stock)
        hist = attribute_history(i, t, '1d', 'close', df=False)
        if context.portfolio.positions[i].avg_cost *0.95 >= hist['close'][0]:
            #亏损 5% 卖出
            list_to_sell.append(stock)
    return list_to_sell
def notBuyThenSell(context, list_to_buy):
    list_to_sell = []
    list_hold = context.portfolio.positions.keys()
    for stock in list_hold:
        if stock not in list_to_buy:
            list_to_sell.append(stock)
    return list_to_sell
#8
# 获得卖出信号
# 输入：context（见API文档）, list_to_buy为list类型，代表待买入的股票
# 输出：list_to_sell为list类型，表示待卖出的股票
def stocks_to_sell(context, list_to_buy):
    # 对于不需要持仓的股票，全仓卖出
    list_to_sell = notBuyThenSell(context, list_to_buy)
    # list_to_sell = get_clear_stock(context, list_to_buy)
    if g.trade_skill:
        list_to_sell2 = stocks_udma_to_sell(context)
        for i in list_to_sell2:
            if i not in list_to_sell:
                list_to_sell.append(i)
    #log.debug(list_to_sell) 
    return list_to_sell

# 平仓，卖出指定持仓
# 平仓成功并全部成交，返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），或者报单非全部成交，返回False
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0) # 可能会因停牌失败
    if order != None:
        if order.filled > 0 and g.flag_stat:
            # 只要有成交，无论全部成交还是部分成交，则统计盈亏
            g.trade_stat.watch(security, order.filled, position.avg_cost, position.price)
    return False
    
    
# 自定义下单
# 根据Joinquant文档，当前报单函数都是阻塞执行，报单函数（如order_target_value）返回即表示报单完成
# 报单成功返回报单（不代表一定会成交），否则返回None
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
        
    # 如果股票停牌，创建报单会失败，order_target_value 返回None
    # 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
    # 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
    return order_target_value(security, value)
    
#9
# 执行卖出操作
# 输入：list_to_sell为list类型，表示待卖出的股票
# 输出：none
def sell_operation(context, list_to_sell):
    for stock_sell in list_to_sell:
        position = context.portfolio.positions[stock_sell]
        close_position(position)


#10
# 执行买入操作
# 输入：context(见API)；list_to_buy为list类型，表示待买入的股票
# 输出：none
def buy_operation(context, list_to_buy):
    for stock_buy in list_to_buy:
        # 为每个持仓股票分配资金
        g.capital_unit=context.portfolio.portfolio_value/g.num_stocks
        # 买入在"待买股票列表"的股票
        order_target_value(stock_buy, g.capital_unit)

'''
================================================================================
每天收盘后
================================================================================
'''
# 每天收盘后做的事情
def after_trading_end(context):
    if g.flag_stat:
        g.trade_stat.report(context)
    return