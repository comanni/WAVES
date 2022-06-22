import traceback
import requests
import csv
import time
import telegram
from telegram.ext import Updater, MessageHandler, Filters
import json
from datetime import datetime
from pprint import pprint

##### 기본 Function #####
def updateJson(filename, data):

    with open("./"+filename +".json", "w", encoding="UTF-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False)

def parseJson(filename):
    with open('./'+filename+'.json', "r") as json_file:
        data = json.load(json_file)
        return data

def appendCsv(fileName, data, fieldName, header=False):
    with open(fileName, "a", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames = fieldName)
        if header == True:
            writer.writeheader()
        if len(data) == 0:
            return
        if str(type(data)) == "<class 'list'>":
            for i in data:
                writer.writerow(i)
        elif str(type(data)) == "<class 'dict'>":
            writer.writerow(data)
        else:
            print("type이 맞지 않습니다. list, dict를 입력하세요")

#################################################
## TELEGRAM INIT
# my_token = parseJson("URL")["my_token"]
## FOR DEV
my_token = parseJson("URL")["my_token"]
bot = telegram.Bot(token=my_token)  # bot을 선언합니다.

updater = Updater(token=my_token, use_context=True)
updater.start_polling(drop_pending_updates=True)
chatId = parseJson("URL")["chat_id"]

## TRACKING FUNCTION
def exportTransaction(id, cursor):
    response = requests.get(f"https://wscan.io/api.php?endpoint=transactions&address={id}&cursor={cursor}&hideSentMassSubTx=1&enableHistoricValues=1")
    nextCursor = response.json()["txs"]["next"]

    print("nextCursor : ",nextCursor)
    
    txs = response.json()["txs"]["data"]
    isLastPage = (response.json()["txs"]["isLastPage"]) # 마지막 페이지인 경우 True
    
    txList = []
    
    # 한번에 200개의 거래 내역을 불러옴. 각 거래내역을 리스트로 정리하여 return
    for tx in txs:
        _tx = {
            "id":id,
            "timestamp":tx["timestamp"],
            "amount":tx["amount"],
            "assetName":tx["assetName"],
            "targetAddress":tx["address"],
            "type":tx["wtype"],
            "hashid":tx["id"],
            "addon":tx["addon"]
        }
        txList.append(_tx)
    return {"nextCursor":nextCursor, "isLastPage":isLastPage, "list":txList}

def sendTelegramMessage(message):
    print("메세지를 발송합니다.")
    pprint(message)
    pprint(message["assetName"] == "USD-N")
    pprint(abs(message["amount"]) >= 5000)
    text = ""
    if message["assetName"] == "WAVES" and abs(message["amount"]) > 5000:
        text += "🚨대규모 거래 탐지\n"
    if message["assetName"] == "USD-N" and abs(message["amount"]) >= 50000:
        text += "🚨대규모 거래 탐지\n"
    if message["assetName"] == "USDT" and abs(message["amount"]) >= 50000:
        text += "🚨대규모 거래 탐지\n"
    if message["assetName"] == "USDC" and abs(message["amount"]) >= 50000:
        text += "🚨대규모 거래 탐지\n"
    text += "지갑명 : " + message["nickname"]
    text += "\nID : " + message["id"]
    text += "\n발생시간 : " + datetime.fromtimestamp(message["timestamp"]/1000).strftime("%Y-%m-%d %H:%M:%S")
    text += "\n수량 : " + str(message["amount"]) + " " + message["assetName"]
    text += "\n종류 : " + message["type"] + " " + message["addon"]
    text += "\n\n" + f"[트랜잭션 확인하기](https://wscan.io/{message['hashid']})"
    
    bot.sendMessage(chat_id="-1001615503634", text=text, parse_mode='markdown',disable_web_page_preview=True)
    # bot.sendMessage(chat_id="158772679", text=text, parse_mode='markdown',disable_web_page_preview=True)


def batchSendTelegram(messageSet):
    print("메세지 발송을 시작합니다.")
    for message in messageSet:
        try:
            sendTelegramMessage(message)
        except:
            time.sleep(30)
            try:
                sendTelegramMessage(message)
            except:
                print("에러로 발송이 되지 않았습니다.")
                print("MESSAGE : ", message)
                print(traceback.format_exc())
        time.sleep(3)
## 반복 Function : 2분마다 반복

if __name__ == "__main__":
    while True:
        idList = parseJson("IDLIST")
        waitTelegramMessage = [] # 텔레그램에 보낼 메세지를 담아두는 array
        print(">>>>>>idList")
        print(idList)
        for walletId in idList:

            # 초기값 설정
            lastUpdate = walletId["lastUpdate"]
            cursor = 999999999
            currentLastUpdate = 0
            _resLast = 0 #현재 조회하고 있는 transaction의 timestamp 저장
            waitingTx = [] # 저장할 transaction 임시 보관

            while True:
                try:
                    print("wallet ID : ", walletId["wallet"])
                    transactions = exportTransaction(walletId["wallet"], cursor) # 거래 내역을 불러옴

                    print("확인되는 거래 갯수 : ", len(transactions["list"]))
                    for tx in transactions["list"]:
                        if tx["timestamp"] > int(lastUpdate):            # 기존 값보다 시간이 흘렀으면
                            tx["nickname"] = walletId["nickname"]   # 해당 TX를 저장한다.
                            waitingTx.append(tx)

                            if tx["timestamp"] > currentLastUpdate: # 최종 TIME STAMP 갱신을 위해 가장 큰값인 경우 저장
                                currentLastUpdate = tx["timestamp"]
                        _resLast = tx["timestamp"] # 현재 진행하고 있는 time stamp 저장

                    print("isLastPage : " , transactions["isLastPage"])
                    print("_resLast: ", _resLast, "lastUpdate: ", lastUpdate)
                    break
                except Exception as e:
                    print(traceback.format_exc())
                    break

            ###### 임시중단
                if transactions["isLastPage"] != False or _resLast < lastUpdate:    # 마지막페이지이거나, 기존 저장했던 영역에 도달했으면
                    break                                                           # while Loop 탈출
                else:
                    cursor = transactions["nextCursor"]                             # 아니면 다음 커서로 이동해서 확인

            ##############
            print(len(waitingTx), "개의 트랜잭션이 추가됩니다.")
            
            waitTelegramMessage.extend(waitingTx)  # 텔레그램 보낼 리스트에 추가
            appendCsv("./waves3.csv", waitingTx, ["id", "nickname", "timestamp", "amount", "assetName", "addon", "targetAddress", "type", "hashid"]) # CSV에 저장
            if currentLastUpdate != 0:
                walletId["lastUpdate"] = currentLastUpdate  # 지갑 리스트에 있는 최종 TX 타임스탬프 갱신

        updateJson("IDLIST", idList) #모든 지갑 체크가 끝난 경우 데이터를 업데이트
        # print(waitTelegramMessage)
        if len(waitTelegramMessage) != 0:
            batchSendTelegram(waitTelegramMessage)
            waitTelegramMessage = []
        time.sleep(120)