import tkinter as tk
import time
import serial
import adafruit_fingerprint
from datetime import datetime
import requests
from urllib.parse import urlencode
from pyfingerprint.pyfingerprint import PyFingerprint
import pymysql

# 시리얼 통신 설정
uart = serial.Serial("/dev/ttyAMA0", baudrate=57600, timeout=1)

# 지문 인식 센서 초기화
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

# URL 주소를 입력해주세요.
WEBHOOK_URL = "http://203.252.168.72:8080/user/attendance"

# 텍스트 초기화용 함수
def clear_message():
    result_label.config(text="")

# 데이터 조회용 창 생성 함수
def show_data():
    data_window = tk.Toplevel(app)
    data_window.title("All Data")
    
    tk.Label(data_window, text="이름", width=30, font=("Arial", 20)).grid(row=0, column=0)
    tk.Label(data_window, text="학번/사번", width=30, font=("Arial", 20)).grid(row=0, column=1)
    tk.Label(data_window, text="저장 위치", width=30, font=("Arial", 20)).grid(row=0, column=2)
    
    try:
        conn = pymysql.connect(host="127.0.0.1", user="a2b2", passwd="a2b2", db="raspi_db")
        cur = conn.cursor()
        cur.execute("SELECT name, id, location FROM finger_template")
        for index, (name, id, location) in enumerate(cur.fetchall()):
            tk.Label(data_window, text=name, width=30, font=("Arial", 16)).grid(row=index+1, column=0)
            tk.Label(data_window, text=id, width=30, font=("Arial", 16)).grid(row=index+1, column=1)
            tk.Label(data_window, text=location, width=30, font=("Arial", 16)).grid(row=index+1, column=2)
    except pymysql.MySQLError as e:
        print(f"데이터베이스 오류: {e}")
    finally:
        if conn:
            conn.close()

# 데이터를 서버에 전송하는 함수
def send_to_server(action, id):
    data = {
        "출근/퇴근": action,
        "학번": id,
    }
    
    formatted_data = {"action": data["출근/퇴근"],
                      "userId": data['학번']}
    
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(WEBHOOK_URL, json=formatted_data, headers=headers)
        if response.status_code != 201:
            print(f"Failed to send data. Status code: {response.status_code}")
        return response.status_code
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

# 지문 등록 함수
def enroll_finger(name, id, location):
    name_input = name_entry.get()
    id_input = id_entry.get()
    location_input = location_entry.get()

    if not name_input:
        result_label.config(text="이름을 입력하세요!", fg='black')
        app.after(3000, clear_message)
        return
    
    elif not id_input:
        result_label.config(text="학번/사번을 입력하세요!", fg='black')
        app.after(3000, clear_message)
        return
    
    elif not location_input:
        result_label.config(text="저장 위치를 입력하세요!", fg='black')
        app.after(3000, clear_message)
        return
    
    conn = pymysql.connect(host="127.0.0.1", user="a2b2", passwd="a2b2", db="raspi_db")

    try:
        f = PyFingerprint('/dev/ttyAMA0', 57600, 0xFFFFFFFF, 0x00000000)
    except Exception as e:
        print('The fingerprint sensor could not be initialized!')
        print('Exception message: ' + str(e))
        exit(1)     

    try:
        while (f.readImage() == False):
            pass
        f.convertImage(0x01)
        characteristics = str(f.downloadCharacteristics(0x01)).encode('utf-8')
        cur = conn.cursor()

        check_using = "SELECT * FROM finger_template WHERE location = %s"
        cur.execute(check_using, (location,))
        existing_record = cur.fetchone()

        if existing_record:
            result_label.config(text="이미 사용중인 위치입니다!", fg='black')
            app.after(3000, clear_message)
        else:
            sql = "INSERT INTO finger_template VALUES (%s, %s, %s, %s)"
            cur.execute(sql, (characteristics, id, location, name))
            conn.commit()
            result_label.config(text="지문 등록 성공!", fg='black')
            app.after(3000, clear_message)
    except Exception as e:
        print('Operation failed!')
        print('Exception message: ' + str(e))
        exit(1)
    finally:
        conn.close()
        name_entry.delete(0, tk.END)
        id_entry.delete(0, tk.END)
        location_entry.delete(0, tk.END)

# get_fingerprint 함수 추가
def get_fingerprint():
    print("Waiting for image...")
    while finger.get_image() != adafruit_fingerprint.OK:
        pass
    print("Templating...")
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        return False
    print("Searching...")
    if finger.finger_search() != adafruit_fingerprint.OK:
        return False
    return True

# 지문 검색 함수
def search_fingerprint():
    try:
        f = PyFingerprint('/dev/ttyAMA0', 57600, 0xFFFFFFFF, 0x00000000)
        if f.verifyPassword() == False:
            raise ValueError('The given fingerprint sensor password is wrong!')

        while f.readImage() == False:
            pass

        f.convertImage(0x01)

        conn = pymysql.connect(host="127.0.0.1", user="a2b2", passwd="a2b2", db="raspi_db")
        cur = conn.cursor()
        sql = "SELECT * FROM finger_template"
        cur.execute(sql)

        best_score = 60
        identified_user = None
        for row in cur.fetchall():
            f.uploadCharacteristics(0x02, eval(row[0]))
            score = f.compareCharacteristics()
            if score > best_score:
                best_score = score
                identified_user = row[3]
                location = row[2];

        if identified_user:
            result_label.config(text=f"저장 위치 {location}번에서 {identified_user} 감지됨", fg='black')
        else:
            result_label.config(text="미등록 사용자 감지됨", fg='black')

    except Exception as e:
        print('Operation failed!')
        print('Exception message: ' + str(e))
        result_label.config(text="지문 검색에 실패함", fg='black')
    finally:
        conn.close()
        app.after(3000, clear_message)

# 지문 삭제 함수
def delete_fingerprint():
    location_input = location_entry.get()
    
    if not location_input:
        result_label.config(text="삭제할 위치를 선택하세요!", fg='black')
        app.after(3000, clear_message)
        return
    
    try:
        location = int(location_input)
    except ValueError:
        result_label.config(text="잘못된 위치 값입니다. 숫자를 입력하세요.", fg='black')
        app.after(3000, clear_message)
        return

    result_label.config(text="삭제중...", fg='black')
    
    try:
        conn = pymysql.connect(host="127.0.0.1", user="a2b2", passwd="a2b2", db="raspi_db")
        cur = conn.cursor()

        sql = "DELETE FROM finger_template WHERE location = %s"
        affected_rows = cur.execute(sql, (location,))
        conn.commit()

        if affected_rows > 0:
            result_label.config(text=f"{location}에 위치한 지문 정보 삭제 완료!", fg='black')
        else:
            result_label.config(text="삭제할 지문 정보가 없습니다.", fg='black')

    except pymysql.MySQLError as e:
        result_label.config(text=f"데이터베이스 오류: {e}")
    except Exception as e:
        result_label.config(text=f"오류 발생: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
        location_entry.delete(0, tk.END)
        app.after(3000, clear_message)
    
# 출근 버튼 클릭 시 실행되는 함수
def clock_in():
    try:
        f = PyFingerprint('/dev/ttyAMA0', 57600, 0xFFFFFFFF, 0x00000000)
        if f.verifyPassword() == False:
            raise ValueError('The given fingerprint sensor password is wrong!')

        while f.readImage() == False:
            pass

        f.convertImage(0x01)

        conn = pymysql.connect(host="127.0.0.1", user="a2b2", passwd="a2b2", db="raspi_db")
        cur = conn.cursor()
        sql = "SELECT * FROM finger_template"
        cur.execute(sql)

        best_score = 60
        identified_user = None
        for row in cur.fetchall():
            f.uploadCharacteristics(0x02, eval(row[0]))
            score = f.compareCharacteristics()
            if score > best_score:
                best_score = score
                identified_id = row[1]
                identified_user = row[3]
                location = row[2]

        if identified_user:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            server_response = send_to_server(1, identified_id)
            if server_response == 201:
                result_label.config(text=f"출근 시간: {current_time}\n{identified_user} 출근 완료", fg='green')
            else:
                result_label.config(text="출근 처리 실패!", fg='red') 
        else:
            result_label.config(text="미등록 사용자 감지됨", fg='orange')

    except Exception as e:
        print('Operation failed!')
        print('Exception message: ' + str(e))
        result_label.config(text="지문 검색에 실패함", fg='yellow')
    finally:
        conn.close()
        app.after(3000, clear_message)

# 퇴근 버튼 클릭 시 실행되는 함수
def clock_out():
    try:
        f = PyFingerprint('/dev/ttyAMA0', 57600, 0xFFFFFFFF, 0x00000000)
        if f.verifyPassword() == False:
            raise ValueError('The given fingerprint sensor password is wrong!')

        while f.readImage() == False:
            pass

        f.convertImage(0x01)

        conn = pymysql.connect(host="127.0.0.1", user="a2b2", passwd="a2b2", db="raspi_db")
        cur = conn.cursor()
        sql = "SELECT * FROM finger_template"
        cur.execute(sql)

        best_score = 60
        identified_user = None
        for row in cur.fetchall():
            f.uploadCharacteristics(0x02, eval(row[0]))
            score = f.compareCharacteristics()
            if score > best_score:
                best_score = score
                identified_id = row[1]
                identified_user = row[3]
                location = row[2]

        if identified_user:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            server_response = send_to_server(0, identified_id)
            if server_response == 201:
                result_label.config(text=f"퇴근 시간: {current_time}\n{identified_user} 퇴근 완료", fg='green')
            else:
                result_label.config(text="퇴근 처리 실패!", fg='red') 
        else:
            result_label.config(text="미등록 사용자 감지됨", fg='orange')

    except Exception as e:
        print('Operation failed!')
        print('Exception message: ' + str(e))
        result_label.config(text="지문 검색에 실패함", fg='yellow')
    finally:
        conn.close()
        app.after(3000, clear_message)

# Tkinter 애플리케이션 생성
app = tk.Tk()
app.title("Fingerprint Management")

# 전체 화면 모드 설정
app.attributes("-fullscreen", True)

# Canvas와 Frame을 사용하여 화면 중앙에 위젯 배치
canvas = tk.Canvas(app)
canvas.pack(fill=tk.BOTH, expand=True)

frame = tk.Frame(canvas)
canvas.create_window((app.winfo_screenwidth() // 2, app.winfo_screenheight() // 2), window=frame)

# 지문 등록 UI 구성
name_label = tk.Label(frame, text="이름:", font=("Arial", 24))
name_label.pack(fill=tk.X, pady=20)

name_entry = tk.Entry(frame, font=("Arial", 24))
name_entry.pack(pady=20, ipadx=30)

# 학번/사번 입력
id_label = tk.Label(frame, text="학번/사번:", font=("Arial", 24))
id_label.pack(fill=tk.X, pady=20)

id_entry = tk.Entry(frame, font=("Arial", 24))
id_entry.pack(pady=20, ipadx=30)

# 지문 저장 위치 입력
location_label = tk.Label(frame, text="저장 위치 선택 (0-127):", font=("Arial", 24))
location_label.pack(fill=tk.X, pady=20)

location_entry = tk.Entry(frame, font=("Arial", 24))
location_entry.pack(pady=20, ipadx=30)

button_frame = tk.Frame(frame)
button_frame.pack(pady=20)

clock_frame = tk.Frame(frame)
clock_frame.pack(pady=20)

# 지문 등록 버튼 생성
enroll_button = tk.Button(button_frame, text="지문 등록", command=lambda: enroll_finger(name_entry.get(), id_entry.get(), location_entry.get()), font=("Arial", 24))
enroll_button.pack(side=tk.LEFT, padx=10)

# 지문 검색 및 삭제 UI 구성
search_button = tk.Button(button_frame, text="지문 검색", command=search_fingerprint, font=("Arial", 24))
search_button.pack(side=tk.LEFT, padx=10)

delete_button = tk.Button(button_frame, text="지문 삭제", command=delete_fingerprint, font=("Arial", 24))
delete_button.pack(side=tk.LEFT, padx=10)

# 메인 화면에 데이터 조회 버튼 추가
show_data_button = tk.Button(button_frame, text="데이터 조회", command=show_data, font=("Arial", 24))
show_data_button.pack(side=tk.LEFT, padx=10)

# 출근 버튼 생성
clock_in_button = tk.Button(clock_frame, text="출근", command=clock_in, font=("Arial", 48), bg="green", height=2, width=10)
clock_in_button.pack(side=tk.LEFT, padx=20, pady=20)

# 퇴근 버튼 생성
clock_out_button = tk.Button(clock_frame, text="퇴근", command=clock_out, font=("Arial", 48), bg="red", height=2, width=10)
clock_out_button.pack(side=tk.LEFT, padx=20, pady=20)

# 결과 표시 레이블
result_label = tk.Label(frame, text="", font=("Arial", 60))
result_label.pack(side=tk.BOTTOM)

# Tkinter 애플리케이션 실행
app.mainloop()
