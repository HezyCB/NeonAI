
import numpy as np
import re
import nltk
from keras.layers import Input, Embedding, LSTM, TimeDistributed, Dense, Bidirectional
from keras.models import Model, load_model
import tflite as tf
from keras.layers import SimpleRNN
from keras.layers import Embedding
from keras.layers import Input, Dense, LSTM, TimeDistributed
from keras.models import Model
from gensim.models import Word2Vec

#Global Variables declaration and intitialization
INPUT_VECTOR_LENGTH = 20
OUTPUT_VECTORLENGTH = 20
minimum_length = 2
maximum_length = 20
sample_size = 30000 
WORD_START = 1
WORD_PADDING = 0

exit_words = [
        'bye', 'goodbye', 'exit', 
        'tata','see you','terminate',
        'Bye', 'Goodbye', 'Exit',
        'Tata','See you','Terminate'
         ]

#Mapping the Ids to lines and splitting the lines by using the delimiter.
def map_linetoID(movie_lines):
    linetoID_mapping = {}
    for line in movie_lines:
        split_line = line.split(' +++$+++ ')
        if len(split_line) == 5:
            linetoID_mapping[split_line[0]] = split_line[4]
    return linetoID_mapping

#Splitting the converstions by the delimiter and creating a list of coversation ID's.
def extract_converstionIDs(conversation_lines):
    conversations = []
    for line in conversation_lines[:-1]:
        split_line = line.split(' +++$+++ ')[-1][1:-1].replace("'","").replace(" ","")
        conversations.append(split_line.split(','))
    return conversations

#Function is used to form pairs of questions and answers.
def extract_quesans_pairs(linetoID_mapping,conversations):
    questions = []
    answers = []
    for con in conversations:
        for i in range(len(con)-1):
            questions.append(linetoID_mapping[con[i]])
            answers.append(linetoID_mapping[con[i+1]])
    return questions,answers

#Function is used to transsfrom the text
#For example I'm gets transformed to I am
def transform_text(input_text):
    input_text = input_text.lower()
    input_text = re.sub(r"I'm", "I am", input_text)
    input_text = re.sub(r"he's", "he is", input_text)
    input_text = re.sub(r"she's", "she is", input_text)
    input_text = re.sub(r"it's", "it is", input_text)
    input_text = re.sub(r"that's", "that is", input_text)
    input_text = re.sub(r"what's", "that is", input_text)
    input_text = re.sub(r"where's", "where is", input_text)
    input_text = re.sub(r"how's", "how is", input_text)
    input_text = re.sub(r"\'ll", " will", input_text)
    input_text = re.sub(r"\'ve", " have", input_text)
    input_text = re.sub(r"\'re", " are", input_text)
    input_text = re.sub(r"\'d", " would", input_text)
    input_text = re.sub(r"\'re", " are", input_text)
    input_text = re.sub(r"won't", "will not", input_text)
    input_text = re.sub(r"can't", "cannot", input_text)
    input_text = re.sub(r"n't", " not", input_text)
    input_text = re.sub(r"'til", "until", input_text)
    input_text = re.sub(r"[-()\"#/@;:<>{}`+=~|]", "", input_text)
    input_text = " ".join(input_text.split())
    return input_text

#Filter the questions and answer. The minimum length is 2 and 
#maximum is 20
def filter_ques_ans(clean_questions,clean_answers):
    short_questions_temp = []
    short_answers_temp = []
    for i, question in enumerate(clean_questions):
        if len(question.split()) >= minimum_length and len(question.split()) <= maximum_length:
            short_questions_temp.append(question)
            short_answers_temp.append(clean_answers[i])
    short_questions = []
    short_answers = []
    for i, answer in enumerate(short_answers_temp):
        if len(answer.split()) >= minimum_length and len(answer.split()) <= maximum_length:
            short_answers.append(answer)
            short_questions.append(short_questions_temp[i])
    return short_questions,short_answers

#Calculate the word count 
def create_vocabulary(tokenized_ques,tokenized_ans):
    vocabulary = {}
    for question in tokenized_ques:
        for word in question:
            if word not in vocabulary:
                vocabulary[word] = 1
            else:
                vocabulary[word] += 1
    for answer in tokenized_ans:
        for word in answer:
            if word not in vocabulary:
                vocabulary[word] = 1
            else:
                vocabulary[word] += 1  
    return vocabulary

#Create the encodings and decodings by assigning unique 
#index to the words.
def create_encoding_decoding(vocabulary):
    threshold = 15
    count = 0
    encoding_skipgram=[]
    for k,v in vocabulary.items():
        if v >= threshold:
            count += 1
    vocab_size  = 2 
    encoding = {}
    decoding = {1: 'START'}
    for word, count in vocabulary.items():
        if count >= threshold:
            encoding[word] = vocab_size 
            decoding[vocab_size ] = word
            encoding_skipgram.append(word)
            vocab_size += 1
    return encoding,decoding,vocab_size,encoding_skipgram

#Convert the training and validation data into vectors
def transform(encoding, data, vector_size=20):
    transformed_data = np.zeros(shape=(len(data), vector_size))
    for i in range(len(data)):
        for j in range(min(len(data[i]), vector_size)):
            try:
                transformed_data[i][j] = encoding[data[i][j]]
            except:
                transformed_data[i][j] = encoding['<UNKNOWN>']
    return transformed_data

#Create skip gram model and apply it on the encoding data.
def create_skipgramEmbeddings(encoding,size,encoding_skipgram):
    skipgram_model = Word2Vec(encoding_skipgram,sg=1)
    embedding_matrix = np.zeros((size, 100))
    for word,index in encoding.items():
        try:
            extractedword=word.lower()
            embedding_matrix[index, :] = skipgram_model.wv[extractedword]
        except: continue
    return embedding_matrix

#Creating the LSTM model
def create_model(dict_size,embed_layer,hidden_dim):
    
    encoder_inputs = Input(shape=(maximum_length, ), dtype='int32',)
    encoder_embedding = embed_layer(encoder_inputs)
    encoder_LSTM = LSTM(hidden_dim, return_state=True)
    encoder_outputs, state_h, state_c = encoder_LSTM(encoder_embedding)
    decoder_inputs = Input(shape=(maximum_length, ), dtype='int32',)
    decoder_embedding = embed_layer(decoder_inputs)
    decoder_LSTM = LSTM(hidden_dim, return_state=True, return_sequences=True)
    decoder_outputs, _, _ = decoder_LSTM(decoder_embedding, initial_state=[state_h, state_c])
    outputs = TimeDistributed(Dense(dict_size, activation='softmax'))(decoder_outputs)
    model = Model([encoder_inputs, decoder_inputs], outputs)
    return model

# predicting the answer to the question
#and returning the output vectors.
def prediction_answer(user_input,model):
    transformed_input = transform_text(user_input)
    input_tokens = [nltk.word_tokenize(transformed_input)]
    input_tokens = [input_tokens[0][::-1]]  #reverseing input seq
    encoder_input = transform(encoding, input_tokens, 20)
    decoder_input = np.zeros(shape=(len(encoder_input), OUTPUT_VECTORLENGTH))
    decoder_input[:,0] = WORD_START
    for i in range(1, OUTPUT_VECTORLENGTH):
        pred_output = model.predict([encoder_input, decoder_input]).argmax(axis=2)
        decoder_input[:,i] = pred_output[:,i]
    return pred_output

#decoding the vectors.
def decode_answer(decoding, ans_vec):
    ans = ''
    for i in ans_vec:
        if i == 0:
            break
        ans += ' '
        ans += decoding[i]
    return ans

linetoID_mapping={}
conversations=[]
#Reading the conversational data
movie_lines = open('/storage/emulated/0/Download/movie_lines.txt', encoding='utf-8', errors='ignore').read().split('\n')
conversation_lines = open('/storage/emulated/0/Download/movie_conversations.txt', encoding='utf-8', errors='ignore').read().split('\n')
#calling map_linetoID()
linetoID_mapping=map_linetoID(movie_lines)
    
#calling extract_converstions()
conversations=extract_converstionIDs(conversation_lines)
    
#extracting question answer pairs
questions,answers=extract_quesans_pairs(linetoID_mapping,conversations)
transformed_ques = []
for question in questions:
    transformed_ques.append( transform_text(question))
transformed_answers = []    
for answer in answers:
     transformed_answers.append(transform_text(answer))
    
#Limiting the length of questionas and answers
filtered_questions=[]
filtered_answers=[]
filtered_questions,filtered_answers=filter_ques_ans(transformed_ques,transformed_answers)
    
#Tokeninzing
filtered_questions = filtered_questions[:sample_size]
filtered_answers = filtered_answers[:sample_size]
#tokenizing the questions and answers
tokenized_ques = [nltk.word_tokenize(sent) for sent in filtered_questions]
tokenized_ans = [nltk.word_tokenize(sent) for sent in filtered_answers]
    
#Splitting the data into training and validation datasets
size = len(tokenized_ques)
training_input  = tokenized_ques[:round(size*(80/100))]
training_input  = [tr_input[::-1] for tr_input in training_input] #reverseing input seq for better performance
training_output = tokenized_ans[:round(size*(80/100))]

# We will use the remaining for validation
validation_input = tokenized_ques[round(size*(80/100)):]
validation_input  = [val_input[::-1] for val_input in validation_input] #reverseing input seq for better performance
validation_output = tokenized_ans[round(size*(80/100)):]

print('Number of Samples used for training:', len(training_input))
print('Number of samples in the validation:', len(validation_input))
    
#creating vacabulary
vocabulary={}
vocabulary=create_vocabulary(tokenized_ques,tokenized_ans)
print("Length of vocabulary:", len(vocabulary))
    
#creating encodings and decodings
dict_size=0
encoding={}
decoding={}
encoding,decoding,dict_size,encoding_skipgram=create_encoding_decoding(vocabulary)
dict_size=dict_size+1
decoding[len(encoding)+2] = '<UNKNOWN>'
encoding['<UNKNOWN>'] = len(encoding)+2
print("The size of the dictionary:",dict_size)
print("The size of encoding:",len(encoding))
print("The size of decoding:",len(decoding))
    
    
#Function call to the transform function
encoded_training_input = transform(
encoding, training_input, vector_size=INPUT_VECTOR_LENGTH)
encoded_training_output = transform(
encoding, training_output, vector_size=OUTPUT_VECTORLENGTH)
print('Shape of Encoded Training Input', encoded_training_input.shape)
print('Shape of Encoded Training Output', encoded_training_output.shape)
    
#For Validation data 
encoded_validation_input = transform(
encoding, validation_input, vector_size=INPUT_VECTOR_LENGTH)
encoded_validation_output = transform(
encoding, validation_output, vector_size=OUTPUT_VECTORLENGTH)
print('Shape of Encoded validation Input', encoded_validation_input.shape)
print('Shape of Encoded validation Output', encoded_validation_output.shape)
    
#Create the skip-gram embedding which will be used as weights for the embedding layer.
tf.keras.backend.clear_session()
embedding_matrix = np.zeros((dict_size, 100))
embedding_matrix= create_skipgramEmbeddings(encoding,dict_size,encoding_skipgram)
print(embedding_matrix.shape)
    
#forming th embedding layer
embed_layer = Embedding(input_dim=dict_size, output_dim=100, trainable=True,)
embed_layer.build((None,))
embed_layer.set_weights([embedding_matrix])
    
#creating model
hidden_dim=300
lstm_model = create_model(dict_size,embed_layer,hidden_dim)
#getting the summary of model
lstm_model.summary()
    
#compiling the model
lstm_model.compile(optimizer='adam', loss ='categorical_crossentropy', metrics = ['accuracy'])
    
training_encoder_input = encoded_training_input
training_decoder_input = np.zeros_like(encoded_training_output)
training_decoder_input[:, 1:] = encoded_training_output[:,:-1]
training_decoder_input[:, 0] = WORD_START
training_decoder_output = np.eye(dict_size)[encoded_training_output.astype('int32')]

validation_encoder_input = encoded_validation_input
validation_decoder_input = np.zeros_like(encoded_validation_output)
validation_decoder_input[:, 1:] = encoded_validation_output[:,:-1]
validation_decoder_input[:, 0] = WORD_START
validation_decoder_output = np.eye(dict_size)[encoded_validation_output.astype('int32')]

#fitting the model
lstm_model.fit(x=[training_encoder_input, training_decoder_input], y=[training_decoder_output],
    validation_data=([validation_encoder_input, validation_decoder_input], [validation_decoder_output]),
          batch_size=64, epochs=100)

lstm_model.save('lstm_model_skipgram_embeddings.h5')

#Printing the sample Questions and answers.
for i in range(20):
    output = prediction_answer(filtered_questions[i],lstm_model)
    print ('Question:', filtered_questions[i])
    print ('Answer:', decode_answer(decoding, output[0]))
    i=i+1

print("Hello! I am E.D.I.T.H")
user_input = input("~")
predicted_seq =  prediction_answer(user_input,lstm_model)
print (decode_answer(decoding, predicted_seq[0]))
while user_input not in exit_words:
    try:
        user_input = input("~")
        if user_input not in exit_words:
            decode_seq = prediction_answer(user_input,lstm_model)
            print (decode_answer(decoding, decode_seq[0]))
        else:
            break
    except EOFError:
        print("Bye")
        exit()



