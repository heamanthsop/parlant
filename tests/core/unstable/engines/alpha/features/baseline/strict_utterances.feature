Feature: Strict Utterance
    Background:
        Given the alpha engine
        And an agent
        And that the agent uses the strict_utterance message composition mode
        And an empty session

    Scenario: The agent fills multiple fields in a veterinary appointment system (strict utterance)
        Given an agent whose job is to schedule veterinary appointments and provide pet care information
        And that the agent uses the strict_utterance message composition mode
        And a customer named "Joanna"
        And a context variable "next_available_date" set to "May 22" for "Joanna"
        And a context variable "vet_name" set to "Dr. Happypaws" for "Joanna"
        And a context variable "clinic_address" set to "155 Pawprint Lane" for "Joanna"
        And an empty session with "Joanna"
        And a guideline to provide the next available appointment details when a customer requests a checkup for their pet
        And a customer message, "I need to schedule a routine checkup for my dog Max. He's a 5-year-old golden retriever."
        And an utterance, "Our next available appointment for {{generative.pet_name}} with {{generative.vet_name}} is on the {{generative.appointment_date}} at our clinic located at {{generative.clinic_address}}. For a {{generative.pet_age}}-year-old {{generative.pet_breed}}, we recommend {{generative.recommended_services}}."
        And an utterance, "We're fully booked at the moment. Please call back next week."
        And an utterance, "What symptoms is your dog experiencing?"
        And an utterance, "Would you prefer a morning or afternoon appointment?"
        And an utterance, "Our next available appointment is next Tuesday. Does that work for you?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains "Max" in the {pet_name} field
        And the message contains "Dr. Happypaws" in the {vet_name} field
        And the message contains "May 22" in the {appointment_date} field
        And the message contains "155 Pawprint Lane" in the {clinic_address} field
        And the message contains "5" in the {pet_age} field
        And the message contains "golden retriever" in the {pet_breed} field
        And the message contains appropriate veterinary services for a middle-aged dog in the {recommended_services} field

    Scenario: Multistep journey is aborted when the journey description requires so (strict utterance) 
        Given a journey titled Reset Password Journey to follow these steps to reset a customers password: 1. ask for their account name 2. ask for their email or phone number 3. Wish them a good day and only proceed if they wish one back to you. Otherwise let them know that the password could not be reset. 4. use the tool reset_password with the provided information 5. report the result to the customer when the customer wants to reset their password
        And an utterance, "What is the name of your account?"
        And an utterance, "can you please provide the email address or phone number attached to this account?"
        And an utterance, "Your password was successfully reset. An email with further instructions will be sent to your address."
        And an utterance, "Your password could not be reset at this time. Please try again later."
        And the tool "reset_password"
        And a customer message, "I want to reset my password"
        And an agent message, "I can help you do just that. What's your username?"
        And a customer message, "it's leonardo_barbosa_1982"
        And an agent message, "Great! And what's the account's associated email address or phone number?"
        And a customer message, "the email is leonardobarbosa@gmail.br"
        And an agent message, "Got it. Before proceeding to reset your password, I wanted to wish you a good day"
        And a customer message, "What? Just reset my password please"
        When processing is triggered
        Then no tool calls event is emitted
        And a single message event is emitted
        And the message contains either that the password could not be reset at this time

    Scenario: Two journeys are used in unison (strict utterance) 
        Given a journey titled Book Flight to ask for the source and destination airport first, the date second, economy or business class third, and finally to ask for the name of the traveler. You may skip steps that are inapplicable due to other contextual reasons. when a customer wants to book a flight
        And an utterance, "Great. Are you interested in economy or business class?"
        And an utterance, "Great. Only economy class is available for this booking. What is the name of the traveler?"
        And an utterance, "Great. What is the name of the traveler?"
        And an utterance, "Great. Are you interested in economy or business class? Also, what is the name of the person traveling?"
        And a journey titled No Economy to remember that travelers under the age of 21 are illegible for business class, and may only use economy when a flight is being booked
        And a customer message, "Hi, I'd like to book a flight for myself. I'm 19 if that effects anything."
        And an agent message, "Great! From and to where would are you looking to fly?"
        And a customer message, "From LAX to JFK"
        And an agent message, "Got it. And when are you looking to travel?"
        And a customer message, "Next Monday"
        When processing is triggered
        Then a single message event is emitted
        And the message contains either asking for the name of the person traveling, or informing them that they can only travel are only eligible for economy class

