import concurrent.futures
from socket import *
import random
import time
import threading
import struct
import concurrent
from Configuration import *
import errno

class Server:

    #----------------------------------------- Server Constructor  ---------------------------------------------------
    def __init__(self):
        self.UDP_socket = socket(AF_INET, SOCK_DGRAM)  # Servers broadcast their announcements with destination port 13117 using UDP
        self.UDP_socket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        self.UDP_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.TCP_socket = socket(AF_INET, SOCK_STREAM) # Connecting to TCP socekt for interaction with cleints
        self.server_port = self.get_available_port()
        self.devNet = self.get_local_ip()
        self.UDP_socket.bind((self.devNet, broadcast_destination_port)) # Bind the UDP socket to the server's address and port

        self.game_started = False
        self.timer = None
        self.udp_broadcast_timer = None
        self.correct_answer_found = False
        self.count_players = 0 
        self.number_of_question_asked = 1

        self.teams_Correct_Answer = []
        self.question_that_asked = []
        self.teams = []
        self.threadsList = []
        self.threads = []   
        self.total_teams_answer = []
        self.team_names = []
        self.teams_total_wins = {}
        self.teams_answers_specific_game = {}
        self.teams_types_answers = {"T":0, "Y":0, "1":0, "F":0, "N":0, "0":0, "":0}

        
    #----------------------------------------- Getting Port and IP  ---------------------------------------------------

    """ Get an available port from the operating system """
    def get_available_port(self):
        while True:
            try:
                time.sleep(0.1) # Reduce CPU usage
                # Create a temporary socket
                temp_socket = socket(AF_INET, SOCK_STREAM)
                # Bind to port 0 to let the OS choose an available port
                temp_socket.bind(('', 0))  
                temp_socket.listen(1)
                # Get the port assigned by the OS   
                _, server_port = temp_socket.getsockname()  
                temp_socket.close()       
                # Check if the port is already in use
                with socket(AF_INET, SOCK_STREAM) as s:
                    if s.connect_ex(('localhost', server_port)) != 0:
                        # Port is available
                        return server_port
                    else:
                        # Port is in use, try again
                        continue   
            except Exception as e:
                print(f"Error getting available port: {e}")
                continue


    """ Get the local IP address of the computer """
    def get_local_ip(self):
        while True:
            try:
                time.sleep(0.2) 
                tempSocket = socket(AF_INET, SOCK_DGRAM) # Open temporary socket for getting the ip address
                tempSocket.connect(("8.8.8.8", 80))  # Connect to Google's DNS server
                ip_address = tempSocket.getsockname()[0]  # Get the IP address 
                tempSocket.close()
                return ip_address
            except Exception as e:
                print(f"Error getting local IP address: {e}")
                continue


    #----------------------------------------- Sending Broadcast Message  ---------------------------------------------------

    """ Sending broadcast of offer to connect the game every 1 sec, until starting the game """
    def send_UDP_broadcast(self):
        if not self.game_started:
            offer_packet = struct.pack("!IB32sH", 0xabcddcba, 0x2, server_name.encode('utf-8'), self.server_port)
            print(f"\033[1;92mServer started, listening on IP address {self.devNet}\033[0m")
            self.UDP_socket.sendto(offer_packet, ('<broadcast>', broadcast_destination_port))
            self.udp_broadcast_timer= threading.Timer(1.0, self.send_UDP_broadcast)
            self.udp_broadcast_timer.start()


    #-----------------------------------------  Server Handle Client Want To Start Game ---------------------------------------------------

    """ Handle a new client (team) the connect to the server (game) """
    def handle_client(self, client_socket, address):

        # Set a timeout for receiving data from the client
        client_socket.settimeout(0.01)
        try:
            # Receive team name from the client and then decode the received bytes into a string using UTF-8 encoding, removing any leading or trailing whitespace.
            team_name = client_socket.recv(buffer_size).decode('utf-8').strip()

            # Checking if the name has been given already so to change it so won't be two equal names
            self.change_team_name_if_exist(team_name)
            
            # Add the new team to the game
            self.teams.append((team_name, address, client_socket))

            # Restart the timer of waiting 10 sec for a player to join the game before starting the game 
            self.timer.cancel()
            self.start_timer()

        except ConnectionResetError:
            # If the connection was reset by the client (indicating disconnection), handle it gracefully
            print("\033[91mClient disconnected unexpectedly.\033[0m")
            return

        except timeout:
            pass

        except Exception as e:
            # Handle other exceptions gracefully
            pass

        

    """ Checking if the name has been given already so to change it so won't be two equal names """
    def change_team_name_if_exist(self, team_name):
        while team_name in self.team_names:
            team_name = team_name + "1"
        return team_name



    """ Restart the timer of waiting 10 sec for a player to join the game before starting the game """
    def start_timer(self):
        self.timer = threading.Timer(10.0, self.start_game)
        self.timer.start()



    #-----------------------------------------  Server Start Game ---------------------------------------------------

    """ Function that starting the game, checking for enough teams, and start the game if it is enough teams """
    def start_game(self):
        # Checking if there are at least two teams in the game
        self.checking_for_enough_teams_to_start_the_game()       
        if len(self.teams) < 2: 
            self.end_game_not_enough_teams()
            return
        
        self.game_started = True
        # Wait for all teams to be connected successfully before starting the game
        for thread in self.threadsList:
            thread.join()

        # Welcome message + first question of the game
        question = self.makeAndsend_the_welcome_message()
        # Waiting the team's answers
        self.get_Answers_From_Teams(question)
        



    """ First checking of enough players so can start the game """
    def checking_for_enough_teams_to_start_the_game(self):
        for team in self.teams:
            client_socket = team[2]
            try:
                # Set a timeout of 0 to check if data is available to receive
                client_socket.settimeout(0)
                # Attempt to receive data from the client socket
                data = client_socket.recv(buffer_size)
            except (OSError, ConnectionResetError) as e:
                if e.errno != errno.EWOULDBLOCK:
                    self.teams.remove(team)
            except Exception:
                pass



    """ If not enough players in the game - end it and trying to start over again """
    def end_game_not_enough_teams(self):
        self.game_started = True
        the_end_game_message = "Less than 2 players joined to the game.\nGame over, sending out offer requests...\n"
        print("\033[93m" + the_end_game_message + "\033[0m")
        for team in self.teams:
            client_socket = team[2]
            try:
                client_socket.sendall(the_end_game_message.encode())
            except ConnectionResetError as e:
                # Handle the case where the client has been disconnected
                self.teams.remove(team)
            except Exception:
                pass
        self.finish_game_and_start_broadcast_again()


    """ Function that make the welcome message and first question of the game """
    def makeAndsend_the_welcome_message(self):
        # Formulate the welcome message
        welcome_message = (f"\nWelcome to the {server_name} server, where we are answering trivia questions about {trivia_topic} \n")
        players_message = "\n".join([f"Player {i + 1}: {team[0]}" for i, team in enumerate(self.teams)])
        welcome_message += players_message + "\n==\n"
        question = self.generate_Trivia_Questions()
        welcome_message += f"\n\nTrue or false: {question[0]}"

        # Send welcome message to all clients
        for team in self.teams:
            client_socket = team[2]
            try:
                message_to_player = f"Your name is - {team[0]}\n" + welcome_message
                client_socket.sendall(message_to_player.encode())
            except ConnectionResetError as e:
                # Handle the case where the client has been disconnected
                print("Error: Client disconnected unexpectedly.")
                self.teams.remove(team)
        
        print("\033[94m" + welcome_message + "\033[0m")
        return question
    


    """ Function that looking for new question and send it to all players """
    def makeAndSend_new_question_that_not_asked(self):
        question = self.generate_Trivia_Questions()
        while question[2] in self.question_that_asked:
            question = self.generate_Trivia_Questions()
        
        teams_answer_message = f"\nTeam's answers - {self.teams_answers_specific_game}\nNo correct answers!\n"
        teams_types_message = f"\nTeam's type's answers - {self.teams_types_answers}\n"
        new_question_message = teams_answer_message + teams_types_message + f"True or false: {question[0]}"

        self.number_of_question_asked += 1
        # Send new question message to all clients
        self.send_message_after_checking_answers(new_question_message)
        
        print("\033[94m" + new_question_message + "\033[0m")
        return question
        


    """ Function that restart the result of the last question """
    def refresh_results_of_last_question(self):
        self.total_teams_answer = []
        self.teams_types_answers = {"T":0, "Y":0, "1":0, "F":0, "N":0, "0":0, "":0}
        self.teams_answers_specific_game = {}



    """ Function that check if there is a correct answer, if not - send new question, if yes - move to game_over function """
    def check_If_Someone_Correct(self):

        # Checking if it is a correct answer
        if len(self.teams_Correct_Answer) > 0:
            self.game_Over()
        
        else:
            # Start by checking if there enough players to send another question or players left the game
            if len(self.teams) > 1: 
                question = self.makeAndSend_new_question_that_not_asked()
                self.refresh_results_of_last_question()
                self.get_Answers_From_Teams(question)

            # If not enough players, move to game_over function
            else:
                if len(self.teams) == 1:
                    self.update_winnings_of_players(self.teams[0][0])
                self.game_Over()
            


    """ Operate threads for each player to let them answer parallel """ 
    def operate_threads_for_players_to_get_answers(self, question):
        for team in self.teams:
            thread = threading.Thread(daemon=True, target=self.check_Answers, args=(question, team[0], team[2]))
            self.threads.append(thread)
            thread.start()



    """ Function that send a message to all players after checking thier answers """
    def send_message_after_checking_answers(self, message):
        for team in self.teams:
            client_socket = team[2]
            try:
                client_socket.sendall(message.encode())
            except ConnectionResetError as e:
                # Handle the case where the client has been disconnected
                print("\033[91mError: Client disconnected unexpectedly.\033[0m")
                self.teams.remove(team)
            except Exception as e:
                    # Handle other exceptions, if needed
                    pass



    """ Update statistics of the answers that players answered at the specific game """
    def update_statistics_of_answers_of_players_to_specefic_question(self):
        for team in self.teams:
            # Players who not answered will get empty string
            if team[0] not in self.teams_answers_specific_game:
                self.teams_answers_specific_game[team[0]] = ""

            # Update the amount answers of each string
            value = self.teams_answers_specific_game[team[0]]
            self.teams_types_answers[value] += 1



    """ Function that get the answers from all of the players and move to check if someone correct """
    def get_Answers_From_Teams(self, question):    

        # Add the question to the question that asked till now in the specific game 
        self.question_that_asked.append(question[2])
        
        # Operate threads for each player to let them answer parallel 
        self.operate_threads_for_players_to_get_answers(question)

        message_round_done = "Done"
   
        # Start timer of 10 sec for the players to answer and checking if - 
        # (1) someone correct \ (2) time passed \ (3) everyone answered \ (4) players left the game and only one or no one in the game
        start_time = time.time()
        while True:
            # (2)                              (2)                                (3)                                                  (4)
            if (self.correct_answer_found) or (time.time() - start_time >= 10) or (len(self.total_teams_answer) == len(self.teams)) or (len(self.teams) < 2):
                self.send_message_after_checking_answers(message_round_done)
                break

            time.sleep(0.1) # To reduce CPU usage

        # Update statistics of the answers that players answered at the specific game
        self.update_statistics_of_answers_of_players_to_specefic_question()
        
        # Function that check if there is a correct answer, if not - send new question, if yes - move to game_over function
        self.check_If_Someone_Correct()

    

    """ Update total winnings of the player """
    def update_winnings_of_players(self, team_name):
        if team_name not in self.teams_total_wins:
            self.teams_total_wins[team_name] = 1
        else:
            self.teams_total_wins[team_name] += 1



    """ Check if the player enter valid answer and update player's answer """
    def valid_answer_player_update_answers_of_players(self,team_answer, team_name):
        if team_answer in ['T', 'F', 'Y', 'N', '0', '1']:
            self.total_teams_answer.append(team_name)
            self.teams_answers_specific_game[team_name] = team_answer



    """ Function that wait for an answer from the player and check if he is correct, if it is - add a win to his total winnings """
    def check_Answers(self, question, team_name, client_socket):
        # Initialize variables
        correct_answer = question[1]
    
        try:
            # Receive input from clients
            client_socket.settimeout(10)
            team_answer = client_socket.recv(buffer_size).decode("utf-8").strip()
            
            # Check if the player enter valid answer and update player's answer
            self.valid_answer_player_update_answers_of_players(team_answer, team_name)

            # Check if the answer is correct
            if ((team_answer == 'T' or team_answer == 'Y' or team_answer == '1') and correct_answer) or ((team_answer == 'F' or team_answer == 'N' or team_answer == '0') and not correct_answer):
                self.teams_Correct_Answer.append(team_name)
                self.correct_answer_found = True

                # Update total winnings of the player
                self.update_winnings_of_players(team_name)  
                
        except ConnectionResetError:
            # Handle disconnection (client disconnected unexpectedly)
            print("\033[91m" + f"{team_name} disconnected unexpectedly." + "\033[0m")
            for team in self.teams:
                if team[0] == team_name:
                    self.teams.remove(team)

        except timeout:
            # Handle timeout exception, if needed
            pass

        except Exception as e:
            # Handle other exceptions, if needed
            pass
        

    #----------------------------------------- Print Statistics ----------------------------------------------------------

    """ Game over message with all of the statistics of the game """
    def printing_statistics_of_the_game(self, the_winner_message, game_over_message):
        teams_answer_message = f"\nTeam's answers - {self.teams_answers_specific_game}\n"
        teams_types_message = f"\nTeam's type's answers - {self.teams_types_answers}\n"
        number_of_question_asked_in_the_specific_game = f"\nnumber of question asked in the specific game - {self.number_of_question_asked}\n"
        total_wins_message = f"\nTeam's wins till now - {self.teams_total_wins}\n"
        print("\033[93m" + f"{teams_answer_message} {teams_types_message} {number_of_question_asked_in_the_specific_game} {total_wins_message}" + "\033[0m")
        
        return the_winner_message + game_over_message + teams_answer_message + teams_types_message + number_of_question_asked_in_the_specific_game + total_wins_message
        

    #----------------------------------------- End Game  ------------------------------------------------------------------


    """ Function that handle while game over - if there is a winner \ players left the game in the middle """
    def game_Over(self):

        if len(self.teams) != 0:
            the_winner_message = ""
            # if there is more than one player so it must have a winner
            if len(self.teams) > 1:
                the_winner_message = f"{self.teams_Correct_Answer[0]} is correct! {self.teams_Correct_Answer[0]} wins!"
                game_over_message = f"\nGame over!\nCongratulations to the winner: {self.teams_Correct_Answer[0]}\n"

            # if there is only ony player
            elif len(self.teams) == 1:
                game_over_message = f"\nEveryone left the game - You won\nGame over!\nCongratulations to the winner: {self.teams[0][0]}\n"

            # Game over message with all of the statistics of the game
            the_end_game_message = self.printing_statistics_of_the_game(the_winner_message, game_over_message)
                
            # Send the message to all players
            self.send_message_after_checking_answers(the_end_game_message)
                
        print("\033[93m" + "Game over, sending out offer requests..." + "\033[0m")
        # finish the game and start over new game
        self.finish_game_and_start_broadcast_again() 
        


    """ Function that finish the game, clear everything and start over new game"""
    def finish_game_and_start_broadcast_again(self):
        self.clear_Game()
        self.udp_broadcast_timer.cancel()
        self.send_UDP_broadcast()
        self.start_waiting_for_players()



    """ Function that clear all needed from the previous game """
    def clear_Game(self):
        self.teams_Correct_Answer = []
        self.question_that_asked = []
        self.teams = []
        self.count_players = 0
        self.game_started = False
        self.correct_answer_found = False
        self.threadsList = []
        self.threads = []   
        self.total_teams_answer = []
        self.teams_types_answers = {"T":0, "Y":0, "1":0, "F":0, "N":0, "0":0, "":0}
        self.teams_answers_specific_game = {}
        self.number_of_question_asked = 1
        self.total_teams_answer= []



    """ Server bind over TCP socket """
    def bind_tcp_socket(self):
        self.TCP_socket.bind(('', self.server_port))
        self.start_waiting_for_players()


    #----------------------------------------- Start Server - client client the connect  ---------------------------------------------------


    """ Server waiting for clients (players) to connect to the game """
    def start_waiting_for_players(self):
        self.TCP_socket.listen()
        self.start_timer()
        while not self.game_started:
            time.sleep(0.1)
            client_socket, address = self.TCP_socket.accept()
            thr = threading.Thread(target=self.handle_client, args=(client_socket, address))
            thr.start()
            self.threadsList.append(thr)



    #----------------------------------------- Create Trivia Questions  ---------------------------------------------------

    """ Questions of the game """
    def generate_Trivia_Questions(self):
        # True trivia questions about Thailand
        true_questions = [
            {"question": "The capital city of Thailand is Bangkok.", "is_true": True, "index": 1},
            {"question": "Thailand was never colonized by a European country.", "is_true": True, "index": 2},
            {"question": "The national sport of Thailand is Muay Thai.", "is_true": True, "index": 3},
            {"question": "Thailand is the only country in Southeast Asia that was never colonized by Europeans.", "is_true": True, "index": 4},
            {"question": "Thailand is known as the 'Land of Smiles.'", "is_true": True, "index": 5},
            {"question": "Pad Thai is a traditional Thai dish made with noodles, eggs, and peanuts.", "is_true": True, "index": 6},
            {"question": "Thailand has a monarchy as its form of government.", "is_true": True, "index": 7},
            {"question": "The official language of Thailand is Thai.", "is_true": True, "index": 8},
            {"question": "Thailand is home to the world's smallest mammal, the bumblebee bat.", "is_true": True, "index": 9},
            {"question": "Thailand has over 1,400 islands.", "is_true": True, "index": 10}
        ]

        # False trivia questions about Thailand
        false_questions = [
            {"question": "The official currency of Thailand is the Baht.", "is_true": True, "index": 11},
            {"question": "Thailand is the largest country in Southeast Asia by land area.", "is_true": True, "index": 12},
            {"question": "The Thai New Year is celebrated in December.", "is_true": True, "index": 13},
            {"question": "Thailand is landlocked and does not have any coastline.", "is_true": True, "index": 14},
            {"question": "The national flower of Thailand is the lotus.", "is_true": True, "index": 15},
            {"question": "The most popular religion in Thailand is Hinduism.", "is_true": True, "index": 16},
            {"question": "Thailand has a total of five UNESCO World Heritage Sites.", "is_true": True, "index": 17},
            {"question": "The Thai script is derived from the Latin alphabet.", "is_true": True, "index": 18},
            {"question": "Bangkok is the only city in Thailand with a population over 1 million.", "is_true": True, "index": 19},
            {"question": "Thailand has a tropical climate with snowfall occurring in some regions.", "is_true": True, "index": 20}
        ]

        # Combine the true and false questions and shuffle the list
        trivia_questions = true_questions + false_questions
        random.shuffle(trivia_questions)
        return trivia_questions[0]['question'], trivia_questions[0]['is_true'], trivia_questions[0]['index']
        


if __name__ == '__main__':
    server = Server()
    server.send_UDP_broadcast()
    server.bind_tcp_socket()
