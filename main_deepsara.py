import copy
import math
import random
import time
import numpy as np
import calculate_metrics
import dql
import nsl_placement
import nsl_request
import substrate_graphs

#  simulation parameters
# seed = 0
repetitions = 33  #  33 تعداد تکرار برای اطمینان از صحت شبیه سازی 
twindow_length = 1 #  با افزایش دوبرابری تایم ویندو تعداد استپها در هر اپیزود نصف میشوند 

embb_arrival_rate = 0
urllc_arrival_rate = 0
miot_arrival_rate = 0 
arrival_rates = [20]  #  [100,80,60,40,30,25,20,15,10,7,5,3,1] #20 نرخ های مختلفی که در هر اپیزود شبیه سازی میشوند 

mean_operation_time = 15

edge_initial = 0
centralized_initial = 0
bw_initial = 0
agente = None

#  RL-specific parameters
episodes = 350   # 240 تعداد اپیزود هایی که برای یادگیری در نظر گرفته شده است 

avble_edge_size = 10
avble_central_size = 10
avble_bw_size = 10

pct_inst_embb_size = 10   # درصد برش های نمونه از نوع embb
pct_inst_urllc_size = 10
pct_inst_miot_size = 10

pct_arriv_embb_size = 10
pct_arriv_urllc_size = 10
pct_arriv_miot_size = 10

# n_states = avble_edge_size*avble_central_size
#  n_states = avble_edge_size*avble_central_size*avble_bw_size
#  n_states = avble_edge_size*avble_central_size*avble_bw_size*pct_inst_embb_size*pct_inst_urllc_size*pct_inst_miot_size
#  تعدا حالاتی که شبکه میتواند داشته باشد در این حالت برابر 10 به توان 9 در نظر گرفته شده است 
n_states = avble_edge_size*avble_central_size*avble_bw_size*pct_inst_embb_size*pct_inst_urllc_size*pct_inst_miot_size*pct_arriv_embb_size*pct_arriv_urllc_size*pct_arriv_miot_size

#  list of tuples of 30 acts
actions = [
(1,1,1),
(0.75,1,1),(1,0.75,1),(1,1,0.75),(1,0.75,0.75),(0.75,1,0.75),
(0.75,1,0.5),(0.5,1,0.75),(1,0.75,0.5),
(0.5,1,1),(1,1,0.5),(1,0.5,1),(0.5,1,0.5),(1,0.5,0.5),
(0.25,1,1),(1,1,0.25),(0.25,1,0.25),(0.1,1,1),(1,1,0.1),(0.1,1,0.1),
(0.25,1,0.1), (0.1,1,0.25), (0.5,1,0.1), (0.1,1,0.5), (0.75,1,0.1), (0.1,1,0.75),
(0.25,1,0.5), (0.5,1,0.25), (0.25,1,0.75), (0.75,1,0.25)  
]

n_actions = len(actions)

class Evento:
    def __init__(self, tipo, inicio, extra, function):
        self.tipo = tipo
        self.inicio = inicio
        self.extra = extra
        self.function = function

    def __str__(self):
        return "("+self.tipo+","+str(self.inicio)+","+str(self.extra)+")"

class Controlador:
    def __init__(self):
        #metricas
        self.total_profit = 0
        self.node_profit=0
        self.link_profit=0
        self.embb_profit = 0
        self.urllc_profit = 0
        self.miot_profit = 0
        self.edge_profit = 0
        self.central_profit = 0

        self.acpt_rate = 0
        self.embb_acpt_rate = 0
        self.urllc_acpt_rate = 0
        self.miot_acpt_rate = 0
        
        self.total_utl = 0
        self.node_utl = 0
        self.link_utl = 0
        self.edge_utl = 0
        self.central_utl = 0
        self.embb_utl = 0
        self.urllc_utl = 0
        self.miot_utl = 0

        self.simulation = Sim()
        self.substrate = {}
        self.agente = None


    def run(self):
        self.simulation.run(self)

class Sim:
    def __init__(self):
        self.eventos = [] # تعداد کل ایونت ها 
        self.total_events = 0
        self.window_req_list = [[],[],[]] #درخواست های هر دسته اسلایس در 3 صف جدا قرار میگیرد.
        #self.window_req_list = []
        self.granted_req_list = []# درخواست های پذیرفته شده 
        self.horario = 0  #  زمان استارت
        self.run_till = -1  
        self.total_reqs = 0  # مجموع درخواست ها 
        self.total_embb_reqs = 0
        self.total_urllc_reqs = 0
        self.total_miot_reqs = 0
        self.attended_reqs = 0   
        self.accepted_reqs = 0
        self.embb_accepted_reqs = 0
        self.urllc_accepted_reqs = 0
        self.miot_accepted_reqs = 0
        self.current_instatiated_reqs = [0,0,0] #[embb,urllc,miot]
                   
    #  تعیین مدت زمان ران شدن 
    def set_run_till(self, t):
        self.run_till = t

    # def set_substrate(self,substrate):
    #     self.substrate = substrate

    #  ساخت رویداد ورودی به شرط چک کردن زمان استارت آن
    #  مقادیر اف و اکسترا خالی میمونن تا بعدا مقدار دهی بشن
    def create_event(self, tipo, inicio, extra=None, f=None):
        if inicio<self.horario:
            print("***false")
            return False
        # else:     
        e = Evento(tipo, inicio, extra, f)
        return e

    #  در آرایه ای که ار و ال ابتدا و انتهای ان هستند به دنبال ایندکسی می گردد که برابر ایکس باشد
    def binary_search (self, arr, l, r, x):
        if r >= l:       
            mid = int(l + (r - l)/2)
            if arr[mid].inicio == x: 
                return mid
            elif arr[mid].inicio > x: 
                return self.binary_search(arr, l, mid-1, x) 
            else: 
                return self.binary_search(arr, mid+1, r, x)   
        else:             
            return l

    #  با توجه به تایم استارت جایگاه درخواست را با استفاده از باینری سرچ مشخص کرده و در آنجا قرار می دهد
    def add_event(self, evt):        

        index = self.binary_search(self.eventos, 0, len(self.eventos)-1, evt.inicio)
        self.eventos = self.eventos[:index] + [evt] + self.eventos[index:] 


        if evt.tipo == "arrival":   #  با توجه به تایپ رخداد که باید از نوع ورود باشد نسبت به دسته بندی آن ها اقدام میکند .           
            self.total_reqs += 1
            service_type = evt.extra["service_type"]
            request = nsl_request.get_nslr(self.total_reqs,service_type,mean_operation_time)  #  با استفاده از ماژول nsl_req ، از فانکشن get_nslr  برای دریافت ریکوئست استفاده میکند .

            if evt.extra["service_type"] == "embb":
                self.total_embb_reqs += 1
                self.window_req_list[0].append(copy.deepcopy(request))  #  به ایندکس
            elif evt.extra["service_type"] == "urllc":
                self.total_urllc_reqs += 1
                self.window_req_list[1].append(copy.deepcopy(request))
            else: #evt.extra["service_type"] == "miot":
                self.total_miot_reqs += 1
                self.window_req_list[2].append(copy.deepcopy(request))



    def print_eventos(self):
        print("HORARIO: ",self.horario,"\nTotal Eventos:",len(self.eventos))
        for i in range(len(self.eventos)): 
            print(self.eventos[i].tipo,self.eventos[i].inicio, end=" > ")
        #print("++list: ",len(self.window_req_list[0])+len(self.window_req_list[1])+len(self.window_req_list[2]))

        print("\n")

    def get_proximo_evento(self):  #  با چک کردن طول لیست در صورت وجود رویداد بعدی آن را پردازش و یکی از درخواست ها حذف می کند .
        if len(self.eventos)==0:
            return None
        else:
            p = self.eventos.pop(0)
            self.horario = p.inicio
            return p

    def run(self,c):  #  تا زمانی که تایم کمتر از زمان پایان شبیه سازی باشد درخواست بعدی را اجرا میکند 
        # self.print_eventos()
        while self.horario<self.run_till:
            #self.print_eventos()
            p = self.get_proximo_evento()
            if p==None:
                return    
            p.function(c,p)
 
def aleatorio(seed):  # اعداد تصادفی در بازه [0, 1)  تولید میکند
    m = 2**34
    c = 251
    a = 4*c+1
    b=351
    rand_number = (((a*seed)+b)%m)/m
    return rand_number

def get_interarrival_time(arrival_rate):  #  با استفاده از اعداد تصادفی ساخته شده و تابع نمایی تایم ورود هر رویداد را ایجاد می کند
    seed = random.randint(10000000,8000000000)
    p = aleatorio(seed) 
    # print(p)     
    inter_arrival_time = -math.log(1.0 - p)/arrival_rate #the inverse of the CDF of Exponential(_lamnbda)
    # inter_arrival_time = float('{0:,.2f}'.format(inter_arrival_time))

    return inter_arrival_time

def filtro(window_req_list,action):
    
    granted_req_list = []
    auxiliar_list = []
    for req in window_req_list:
        if (req.service_type == "embb" and req.bandera <= actions[action][0]*100) or (req.service_type == "urllc" and req.bandera <= actions[action][1]*100) or (req.service_type == "miot" and req.bandera <= actions[action][2]*100):  #  باندرا عددی رندم بین 1 تا 100 است که هر درخواست اسلایسینگ آن را داراست که این عدد با اکشن های تعریف شده مقایسه میشود
            # print("**agregando request...")  # اگر اکشن کمتر از باندرای تصادفی ای که برای اسلایس انتخاب شده باشد درخواست رد می شود 
            granted_req_list.append(req)
    #     else:
    #         auxiliar_list.append(req)

    # granted_req_list = granted_req_list + auxiliar_list 

    return granted_req_list
    
def takeFirst(elem):
    return elem[0]
    
def prioritizer(window_req_list,action_index):   #  لیست درخواست ها به همراه اکشن را گرفته و دو لیست درخواست های پذیرفته شده و باقی مانده را بازمیگرداند
    #print("****prioritizing...")
    action = actions[action_index]  #  [0.75,0.75,0]
    action2 = []  #  [[], [], []] به صورت دسته شده از یزرگ به کوچک در هر ایندکس، هر ایندکس برای یک اسلایس است 
    granted_req_list = []
    remaining_req_list = []
    
    #action = (0.75,1,0.25) -> (cant1,cant2,cant3) 
    #اکشن را از درصد به عدد صحیحی که از حاصل ضرب طول بدست آمده رند میکند 
    action2.append([action[0],round(action[0]*len(window_req_list[0])),0]) #[pctg,cant1,tipo] ej:[0.75,75,0]
    action2.append([action[1],round(action[1]*len(window_req_list[1])),1])
    action2.append([action[2],round(action[2]*len(window_req_list[2])),2])

    #از بزرگ به کوچک دسته بندی می کند 
    action2.sort(key=takeFirst,reverse=True)

    for j in action2:
        
        if j[0]==1:
            granted_req_list += window_req_list[j[2]]
            
        else:    
            for i in range(len(window_req_list[j[2]])):            
                if i < j[1]:
                    granted_req_list.append(window_req_list[j[2]][i])
                else:
                    remaining_req_list.append(window_req_list[j[2]][i])      

    return granted_req_list, remaining_req_list #v6
    #return granted_req_list+remaining_req_list, remaining_req_list #v1

def update_resources(substrate,nslr,kill):   #   مسئول به روز رسانی تخصیص منابع در یک شبکه است که در دو بخش وی ان اف ها و لینک ها آن را انجام میدهد 
    
    nodes = substrate.graph["nodes"]
    links = substrate.graph["links"]   
    for vnf in nslr.nsl_graph_reduced["vnodes"]: 
        if "mapped_to" in vnf:
            n = next(n for n in nodes if (n["id"] == vnf["mapped_to"] and n["type"]==vnf["type"]) ) 
            if vnf["type"] == 0:
                tipo = "centralized_cpu"
            else:
                tipo = "edge_cpu"
            if kill: #  در صورت کیل منابع ازاد میشوند 
                
                n["cpu"] = n["cpu"] + vnf["cpu"]
                substrate.graph[tipo] += vnf["cpu"]
            else:
                
                n["cpu"] = n["cpu"] - vnf["cpu"] 
                substrate.graph[tipo] -= vnf["cpu"]
    for vlink in nslr.nsl_graph_reduced["vlinks"]:
        try:  #  اگر در یک گره باشند دیگر لینکی لازم ندارند
            path = vlink["mapped_to"]            
        except KeyError:
            path=[]
        for i in range(len(path)-1):
            try:
                #  اگر بتونه لینکی با مشخصات مشخص شده پیدا بکند که لینک ساخته میشود در غیر اینصورت و با بررسی تمام لینک ها ، ایتریشن متوقف میشود
                l = next(l for l in links if ( (l["source"]==path[i] and l["target"]==path[i+1]) or (l["source"]==path[i+1] and l["target"]==path[i]) ) )              
                if kill:
                    l["bw"] += vlink["bw"]
                    substrate.graph["bw"] += vlink["bw"]
                else:
                    l["bw"] -= vlink["bw"]
                    substrate.graph["bw"] -= vlink["bw"]
            except StopIteration:
                pass

def resource_allocation(cn): #  cn=controller   #  در این قسمت با توجه به منابع تخصیص داده شده میزان سود با توجه به فرموا مورد نظر محاسبه می شود 
    #  makes allocation for the set of nslrs captured in a time window
    #  the metrics calculated here correspond to a step
     
    sim = cn.simulation
    substrate = cn.substrate
    step_embb_profit = 0 
    step_urllc_profit = 0
    step_miot_profit = 0
    step_link_profit=0
    step_node_profit=0
    step_edge_profit = 0
    step_central_profit = 0
    step_profit=0
    step_edge_cpu_utl = 0
    step_central_cpu_utl = 0
    step_links_bw_utl = 0
    step_node_utl = 0
    step_total_utl = 0
    end_simulation_time = sim.run_till
    max_node_profit = substrate.graph["max_cpu_profit"]*sim.run_till
    max_link_profit = substrate.graph["max_bw_profit"]*sim.run_till
    max_profit = max_link_profit + max_node_profit

    for req in sim.granted_req_list:
        # print("**",req.service_type,req.nsl_graph)
        sim.attended_reqs += 1        
        rejected = nsl_placement.nsl_placement(req,substrate)#mapping
        if not rejected: 
            #  در صورتی رد نشود به رویداد ها اضافه می شود 
            req.set_end_time(sim.horario+req.operation_time)
            graph = req.nsl_graph_reduced
            update_resources(substrate,req,False)#instantiation, ocupar recursos
            evt = sim.create_event(tipo="termination",inicio=req.end_time, extra=req, f=func_terminate)
            sim.add_event(evt) 

            #  محاسبه معیارها (سود، نرخ_پذیرش، شمارنده)           
            sim.accepted_reqs += 1
            profit_nodes = calculate_metrics.calculate_profit_nodes(req,end_simulation_time)
            profit_links = calculate_metrics.calculate_profit_links(req,end_simulation_time)*10    
            step_profit += (profit_nodes + profit_links)/max_profit #  the total profit in this step is the reward
            step_link_profit += profit_links/max_link_profit
            step_node_profit += profit_nodes/max_node_profit
            step_edge_profit = 0 #  قابل تنظیم به صورت دلخواه 
            step_central_profit = 0 #   قابل تنظیم به صورت دلخواه 

            if req.service_type == "embb":
                sim.current_instatiated_reqs[0] += 1
                sim.embb_accepted_reqs += 1
                step_embb_profit += profit_nodes/max_node_profit
            elif req.service_type == "urllc":
                sim.current_instatiated_reqs[1] += 1
                sim.urllc_accepted_reqs += 1
                step_urllc_profit += profit_nodes/max_node_profit
            else:
                sim.current_instatiated_reqs[2] += 1
                sim.miot_accepted_reqs += 1
                step_miot_profit += profit_nodes/max_node_profit                       
            
            a,b,c = calculate_metrics.calculate_request_utilization(req,end_simulation_time,substrate)
            step_edge_cpu_utl += a/(edge_initial*end_simulation_time)
            step_central_cpu_utl += b/(centralized_initial*end_simulation_time)
            step_links_bw_utl += c*10/(bw_initial*end_simulation_time)
            step_node_utl += (a+b)/((edge_initial+centralized_initial)*end_simulation_time)
            #step_total_utl += (a+b+(c*10))/((edge_initial+centralized_initial+bw_initial)*end_simulation_time)
            step_total_utl += (step_node_utl + step_links_bw_utl)/2
             
    return step_profit,step_node_profit,step_link_profit,step_embb_profit,step_urllc_profit,step_miot_profit,step_total_utl,step_node_utl,step_links_bw_utl,step_edge_cpu_utl,step_central_cpu_utl

def get_code(value):
    cod = 0
    value = value*100
    if value <= 10:
        cod = 0
    elif value <= 20:
        cod = 1
    elif value <= 30:
        cod = 2
    elif value <= 40:
        cod = 3
    elif value <= 50:
        cod = 4
    elif value <= 60:
        cod = 5        
    elif value <= 70:
        cod = 6
    elif value <= 80:
        cod = 7
    elif value <= 90:
        cod = 8
    else:
        cod = 9
    return cod

def translateStateToIndex(state):  
    '''
هدف این تابع ایجاد یک شاخص منحصر به فرد برای یک وضعیت معین بر اساس پارامترهای مختلف آن است.
    '''
    cod_avble_edge = state[0]
    cod_avble_central = state[1]
    cod_avble_bw = state[2]
    
    cod_pct_embb = state[3]
    cod_pct_urllc = state[4]
    cod_pct_miot = state[5]
    
    cod_pct_arriv_embb = state[6]
    cod_pct_arriv_urllc = state[7]
    cod_pct_arriv_miot = state[8]

    #index = cod_avble_edge*avble_central_size + cod_avble_central
    
    #index for a 3-parameter state
    #index = cod_avble_edge*avble_central_size*avble_bw_size + cod_avble_central*avble_bw_size + cod_avble_bw
    
    #index for a 6-parameter state
    # index = cod_avble_edge*avble_central_size*avble_bw_size*pct_inst_embb_size*pct_inst_urllc_size*pct_inst_miot_size 
    # + cod_avble_central*avble_bw_size*pct_inst_embb_size*pct_inst_urllc_size*pct_inst_miot_size
    # + cod_avble_bw*pct_inst_embb_size*pct_inst_urllc_size*pct_inst_miot_size
    # + cod_pct_embb*pct_inst_urllc_size*pct_inst_miot_size
    # + cod_pct_urllc*pct_inst_miot_size 
    # + cod_pct_miot

    #index for a 9-parameter state
    index = cod_avble_edge*avble_central_size*avble_bw_size*pct_inst_embb_size*pct_inst_urllc_size*pct_inst_miot_size*pct_arriv_embb_size*pct_arriv_urllc_size*pct_arriv_miot_size 
    + cod_avble_central*avble_bw_size*pct_inst_embb_size*pct_inst_urllc_size*pct_inst_miot_size*pct_arriv_embb_size*pct_arriv_urllc_size*pct_arriv_miot_size
    + cod_avble_bw*pct_inst_embb_size*pct_inst_urllc_size*pct_inst_miot_size*pct_arriv_embb_size*pct_arriv_urllc_size*pct_arriv_miot_size
    + cod_pct_embb*pct_inst_urllc_size*pct_inst_miot_size*pct_arriv_embb_size*pct_arriv_urllc_size*pct_arriv_miot_size
    + cod_pct_urllc*pct_inst_miot_size *pct_arriv_embb_size*pct_arriv_urllc_size*pct_arriv_miot_size
    + cod_pct_miot*pct_arriv_embb_size*pct_arriv_urllc_size*pct_arriv_miot_size
    + cod_pct_arriv_embb*pct_arriv_urllc_size*pct_arriv_miot_size
    + cod_pct_arriv_urllc*pct_arriv_miot_size
    + cod_pct_arriv_miot

    return int(index)


def get_state(substrate,simulation):    # لیستی با 9 ایندکس سامل اعداد 0 تا 9 میسازه و با توجه به این حالات  در تابع فوق ایندکسی به دست می آید  
    cod_avble_edge = get_code(substrate.graph["edge_cpu"]/edge_initial)
    cod_avble_central = get_code(substrate.graph["centralized_cpu"]/centralized_initial)
    cod_avble_bw = get_code(substrate.graph["bw"]/bw_initial)
    

    total = 0
    for i in simulation.current_instatiated_reqs:
        total += i
    if total == 0:
        pct_embb, pct_urllc, pct_miot = 0,0,0
    else:
        pct_embb, pct_urllc, pct_miot = simulation.current_instatiated_reqs[0]*100/total,simulation.current_instatiated_reqs[1]*100/total,simulation.current_instatiated_reqs[2]*100/total 
    cod_pct_embb = get_code(pct_embb)
    cod_pct_urllc = get_code(pct_urllc)
    cod_pct_miot = get_code(pct_miot)

    
    contador = [0,0,0]
    n = len(simulation.granted_req_list)
    
    if n == 0:
        pct_arriv_embb, pct_arriv_urllc, pct_arriv_miot = 0,0,0
    else:
        for req in simulation.granted_req_list:
            if req.service_type == "embb":
                contador[0] += 1
            elif req.service_type == "urllc":
                contador[1] += 1
            else:
                contador[2] += 1
        pct_arriv_embb, pct_arriv_urllc, pct_arriv_miot = contador[0]*100/n, contador[1]*100/n, contador[2]*100/n

    cod_pct_arriv_embb = get_code(pct_arriv_embb)
    cod_pct_arriv_urllc = get_code(pct_arriv_urllc)
    cod_pct_arriv_miot = get_code(pct_arriv_miot)


    #3-parameter state:
    #state = [np.float32(cod_avble_edge),np.float32(cod_avble_central),np.float32(cod_avble_bw)]

    #6-parameter state:    
    # state = [
    #             np.float32(cod_avble_edge),
    #             np.float32(cod_avble_central),
    #             np.float32(cod_avble_bw),
    #             np.float32(cod_pct_embb),
    #             np.float32(cod_pct_urllc),
    #             np.float32(cod_pct_miot)
    #         ]

    #9-parameter state:
    state = [
                np.float32(cod_avble_edge),
                np.float32(cod_avble_central),
                np.float32(cod_avble_bw),
                np.float32(cod_pct_embb),
                np.float32(cod_pct_urllc),
                np.float32(cod_pct_miot),
                np.float32(cod_pct_arriv_embb),
                np.float32(cod_pct_arriv_urllc),
                np.float32(cod_pct_arriv_miot)
            ]

    return state
  #   سه حالت در نظر میگیریم برای ایونت ها : یک ورودی دو پایانی و سه تایم ویندو 
def func_arrival(c,evt): # در این تابع درخواست اطلاعات درخواست ورودی ثبت می شود 
    s = c.simulation
    # print("**/",evt.extra["arrival_rate"])
    arrival_rate = evt.extra["arrival_rate"]
    service_type = evt.extra["service_type"]
    inter_arrival_time = get_interarrival_time(arrival_rate)
    s.add_event(s.create_event(tipo="arrival",inicio=s.horario+inter_arrival_time, extra={"service_type":service_type,"arrival_rate":arrival_rate}, f=func_arrival))


contador_termination = 0

def func_terminate(c,evt):  # با اجرای این تابع یک رویداد به کارش پایان میده و منابع آزاد می شوند 
    global contador_termination
    sim = c.simulation
    contador_termination +=1
    print("terminating")
    request = evt.extra
    update_resources(c.substrate,request,True)
    if request.service_type == "embb":
        sim.current_instatiated_reqs[0] -= 1
    elif request.service_type == "urllc":
        sim.current_instatiated_reqs[1] -= 1
    else:
        sim.current_instatiated_reqs[2] -= 1

contador_windows = 0
def func_twindow(c,evt):  #  پس از بررسی استیت با توجه به آن اکشن مناسب را انتخاب و به بخش تخصیص منابع میفرستد 
    #  the time sale has expired. The nslrs collected so far will be analyzed for admission.
    global contador_windows
    sim = c.simulation 
    contador_windows += 1
    
    if evt.extra["first_state"]:
        #first state index
        #all resources at 100% (with granularity of 5)
        state = get_state(c.substrate,c.simulation)
        
        #s = translateStateToIndex(state)
        #a = agente.take_action(s,True)
        
        a = agente.step(state,0)
    else:
        s = evt.extra["current_state"]
        a = evt.extra["action"]
        #print("##agent",agente.last_state," ",agente.last_action)        
      
    sim.granted_req_list, remaining_req_list = prioritizer(sim.window_req_list, a) #  the list of reqs is filtered depending on the action
    #  the list is sent to the Resource Allocation module
    step_profit,step_node_profit,step_link_profit,step_embb_profit,step_urllc_profit,step_miot_profit,step_total_utl,step_node_utl,step_links_bw_utl,step_edge_cpu_utl,step_central_cpu_utl = resource_allocation(c)
    c.total_profit += step_profit
    c.node_profit += step_node_profit
    c.link_profit += step_link_profit
    c.embb_profit += step_embb_profit
    c.urllc_profit += step_urllc_profit
    c.miot_profit += step_miot_profit
    c.total_utl += step_total_utl
    c.node_utl += step_node_utl 
    c.edge_utl += step_edge_cpu_utl 
    c.central_utl += step_central_cpu_utl
    c.link_utl += step_links_bw_utl
    
    r = step_profit
    next_state = get_state(c.substrate,c.simulation) #getting the next state    
    
    #s_ = translateStateToIndex(next_state) #getting index of the next state
    #a_ = agente.take_action(s_,False) #select action for the next state    
    #agente.updateQ(step_profit,s,a,s_,a_,evt.extra["end_state"]) #(reward,s,a,s_,a_end_sate)
    
    s_ = next_state
    a_ = agente.step(s_,r)
    
    a = a_
    s = s_
    if contador_windows  == (sim.run_till/twindow_length) :  #  in original code: - 2
        end_state = True
    else:
        end_state = False
    
    evt = sim.create_event(tipo="twindow_end",inicio=sim.horario+twindow_length, extra={"first_state":False,"end_state":end_state,"current_state":s,"action":a}, f=func_twindow)    
    sim.add_event(evt)
    sim.window_req_list = [[],[],[]] #
    #sim.window_req_list = []
    sim.granted_req_list = [] 
  #  چهار ایونت داریم که سه تای اون مربوط به سه اسلایس مختلف و برای حالت ورودی هست و یکی هم مربوط به تایم ویندو که تایم ویندو در نهایت منجر به حالت پایانی که در بالا ذکر شده می شود   
def prepare_sim(s):
    evt = s.create_event(tipo="arrival",inicio=s.horario+get_interarrival_time(embb_arrival_rate),extra={"service_type":"embb","arrival_rate":embb_arrival_rate},f=func_arrival)
    s.add_event(evt)
    evt = s.create_event(tipo="arrival",inicio=s.horario+get_interarrival_time(urllc_arrival_rate),extra={"service_type":"urllc","arrival_rate":urllc_arrival_rate},f=func_arrival)
    s.add_event(evt)
    evt = s.create_event(tipo="arrival",inicio=s.horario+get_interarrival_time(miot_arrival_rate),extra={"service_type":"miot","arrival_rate":miot_arrival_rate},f=func_arrival)
    s.add_event(evt)

    evt = s.create_event(tipo="twindow_end",inicio=s.horario+twindow_length,extra={"first_state":True,"end_state":False},f=func_twindow)
    s.add_event(evt)


                                
def main():

    global edge_initial
    global centralized_initial
    global bw_initial
    global agente
    global embb_arrival_rate
    global urllc_arrival_rate
    global miot_arrival_rate
    
    for m in arrival_rates:
        embb_arrival_rate = m/3
        urllc_arrival_rate = m/3
        miot_arrival_rate = m/3        
        
        total_profit_rep = []
        link_profit_rep = []
        node_profit_rep = []
        edge_profit_rep = []
        central_profit_rep = []
        profit_embb_rep = []
        profit_urllc_rep = []
        profit_miot_rep = []
        
        acpt_rate_rep = []
        acpt_rate_embb_rep = []
        acpt_rate_urllc_rep = []
        acpt_rate_miot_rep = []

        total_utl_rep = []
        link_utl_rep = []
        node_utl_rep = []
        edge_ult_rep = []
        central_utl_rep = []
        embb_utl_rep = []
        urllc_utl_rep = []
        miot_utl_rep = []    
        
        for i in range(episodes):  #  هر بار رپیتیشن شامل تعدادی مشخص اپیزود است که آن را تعیین میکنیم و در ادامه با توجه به تایم ویندو تعداد استپ در هر اپیزود مشخص می شود 
            total_profit_rep.append([])
            link_profit_rep.append([])
            node_profit_rep.append([])
            edge_profit_rep.append([])
            central_profit_rep.append([])
            profit_embb_rep.append([])
            profit_urllc_rep.append([])
            profit_miot_rep.append([])
            
            acpt_rate_rep.append([])
            acpt_rate_embb_rep.append([])
            acpt_rate_urllc_rep.append([])
            acpt_rate_miot_rep.append([])

            total_utl_rep.append([])
            link_utl_rep.append([])
            node_utl_rep.append([])
            edge_ult_rep.append([])
            central_utl_rep.append([])
            embb_utl_rep.append([])
            urllc_utl_rep.append([])
            miot_utl_rep.append([])
        
        for i in range(repetitions):  # در مقاله 33 بار تکرار کرده است 
            #agente = ql.Qagent(0.9, 0.9, 0.9, episodes, n_states, n_actions) #(alpha, gamma, epsilon, episodes, n_states, n_actions)
            agente = dql.Agent(9,n_actions) # پارامتر اول تعداد حالات که اینجا برابر نه و پارامتر دوم تعداد اکشن ها است که برابر سی است 

            for j in range(episodes):
                agente.handle_episode_start()  #   در ماژول دی کیو ال 

                print("\n","episode:",j,"\n")
                controller = None
                controller = Controlador()                   
                controller.substrate = copy.deepcopy(substrate_graphs.get_graph("16node_BA")) #get substrate  
                # controller.substrate = copy.deepcopy(substrate_graphs.get_graph("abilene")) #get substrate    
                edge_initial = controller.substrate.graph["edge_cpu"]
                centralized_initial = controller.substrate.graph["centralized_cpu"]
                bw_initial = controller.substrate.graph["bw"]
                controller.simulation.set_run_till(15)   #  مدت زمان اجرا را نشان میدهد و بر تعداد تایم ویندو تقسیم می شود
                prepare_sim(controller.simulation)     #  از کلاس کنترالادور تابع سیمولیشن و سپس تابع سیم فراخوانی و در پریپیر سیمولیشن قرار می گیرد       
                controller.run()        

                total_profit_rep[j].append(controller.total_profit)
                node_profit_rep[j].append(controller.node_profit)        
                link_profit_rep[j].append(controller.link_profit)
                edge_profit_rep[j].append(controller.edge_profit)
                central_profit_rep[j].append(controller.central_profit)
                profit_embb_rep[j].append(controller.embb_profit)
                profit_urllc_rep[j].append(controller.urllc_profit)
                profit_miot_rep[j].append(controller.miot_profit)
                        
                acpt_rate_rep[j].append(controller.simulation.accepted_reqs/controller.simulation.total_reqs)
                acpt_rate_embb_rep[j].append(controller.simulation.embb_accepted_reqs/controller.simulation.total_embb_reqs)
                acpt_rate_urllc_rep[j].append(controller.simulation.urllc_accepted_reqs/controller.simulation.total_urllc_reqs)
                acpt_rate_miot_rep[j].append(controller.simulation.miot_accepted_reqs/controller.simulation.total_miot_reqs)
                
                total_utl_rep[j].append(controller.total_utl)
                link_utl_rep[j].append(controller.link_utl)
                node_utl_rep[j].append(controller.node_utl)
                edge_ult_rep[j].append(controller.edge_utl)
                central_utl_rep[j].append(controller.central_utl) 
                embb_utl_rep[j].append(controller.embb_utl)
                urllc_utl_rep[j].append(controller.urllc_utl)
                miot_utl_rep[j].append(controller.miot_utl)

            f = open("deepsara_"+str(m)+"_16BA_9de10sta_30actv22_wWWWW2_maxexpl05_btchsz15_rpsrtsz400_anrate1-400_1h150ns_350epi_prioritizerv6.txt","w+")

            f.write("Repetition: "+str(i)+"\n")
            f.write("**Reward:\n")
            f.write(str(total_profit_rep)+"\n\n")
            f.write("**node_profit_rep:\n")
            f.write(str(node_profit_rep)+"\n\n")
            f.write("**link_profit_rep:\n")
            f.write(str(link_profit_rep)+"\n\n")
            f.write("**edge_profit_rep:\n")
            f.write(str(edge_profit_rep)+"\n\n")
            f.write("**central_profit_rep:\n")
            f.write(str(central_profit_rep)+"\n\n")
            f.write("**profit_embb_rep:\n")
            f.write(str(profit_embb_rep)+"\n\n")
            f.write("**profit_urllc_rep:\n")
            f.write(str(profit_urllc_rep)+"\n\n")
            f.write("**profit_miot_rep:\n")
            f.write(str(profit_miot_rep)+"\n\n")

            f.write("**Acceptance Rate:\n")
            f.write(str(acpt_rate_rep)+"\n\n")
            f.write("**acpt_rate_embb_rep:\n")
            f.write(str(acpt_rate_embb_rep)+"\n\n")
            f.write("**acpt_rate_urllc_rep:\n")
            f.write(str(acpt_rate_urllc_rep)+"\n\n")
            f.write("**acpt_rate_miot_rep:\n")
            f.write(str(acpt_rate_miot_rep)+"\n\n")

            f.write("**total_utl_rep:\n")
            f.write(str(total_utl_rep)+"\n\n")
            f.write("**node_utl_rep:\n")
            f.write(str(node_utl_rep)+"\n\n")
            f.write("**link_utl_rep:\n")
            f.write(str(link_utl_rep)+"\n\n")
            f.write("**edge_ult_rep:\n")
            f.write(str(edge_ult_rep)+"\n\n")
            f.write("**central_utl_rep:\n")
            f.write(str(central_utl_rep)+"\n\n")
            f.write("**embb_utl_rep:\n")
            f.write(str(embb_utl_rep)+"\n\n")
            f.write("**urllc_utl_rep:\n")
            f.write(str(urllc_utl_rep)+"\n\n")
            f.write("**miot_utl_rep:\n")
            f.write(str(miot_utl_rep)+"\n\n")        
            f.close()

if __name__ == '__main__':
    start = time.time()
    main()
    end = time.time()

