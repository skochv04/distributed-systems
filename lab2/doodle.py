from fastapi import Body, FastAPI, status
from typing import Union
from pydantic import BaseModel
from typing import List, Dict
from fastapi.responses import JSONResponse

app = FastAPI()


class Poll(BaseModel):
    question: str
    description: Union[str, None] = None
    options: List[str]


class Vote(BaseModel):
    user_id: str
    option: str


polls_db: Dict[str, Poll] = {}
votes_db: Dict[str, Dict[str, str]] = {}  # {poll_id: {user_id: selected_option}}

last_poll_id = 0


@app.get("/polls/")
async def get_polls(skip: int = 0, limit: int = 10):
    if not polls_db:
        return {"message": "No polls found"}

    poll_ids = list(polls_db.keys())
    selected_polls = poll_ids[skip: skip + limit]

    return [{"id": poll_id, "question": polls_db[poll_id].question, "description": polls_db[poll_id].description,
             "options": polls_db[poll_id].options}
            for poll_id in selected_polls]


@app.get("/polls/{poll_id}")
async def get_poll(poll_id: str):
    if poll_id not in polls_db:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Poll not found"})

    poll = polls_db[poll_id]
    return {"poll_id": poll_id, **poll.dict()}


@app.delete("/polls/{poll_id}")
async def delete_poll(poll_id: str):
    if poll_id in polls_db:
        del polls_db[poll_id]
        votes_db.pop(poll_id, None)
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT)
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Poll not found"})


@app.post("/polls/")
async def create_poll(poll: Poll):
    global last_poll_id

    last_poll_id += 1
    poll_id = str(last_poll_id)

    polls_db[poll_id] = poll

    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"id": poll_id, **poll.dict()})


@app.put("/polls/{poll_id}")
async def update_poll(poll_id: str, question: Union[str, None] = Body(default=None),
                      description: Union[str, None] = Body(default=None),
                      options: Union[List[str], None] = Body(default=None)):
    if poll_id not in polls_db:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Poll not found"})

    if sum(votes_db.get(poll_id, {}).values()) > 0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"message": "There are votes for this poll"})

    # update only if there are no votes
    poll = polls_db[poll_id]
    updated_poll = poll.copy(update={
        "question": question if question is not None else poll.question,
        "description": description if description is not None else poll.description,
        "options": options if options is not None else poll.options,
    })
    polls_db[poll_id] = updated_poll

    return updated_poll


@app.post("/polls/{poll_id}/vote/")
async def add_vote(poll_id: str, vote: Vote):
    if poll_id not in polls_db:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Poll not found"})

    if vote.option not in polls_db[poll_id].options:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid option"})

    if poll_id not in votes_db:
        votes_db[poll_id] = {}

    if vote.user_id in votes_db[poll_id]:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "User has already voted"})

    votes_db[poll_id][vote.user_id] = vote.option

    return {"message": "Vote successfully added", "poll_id": poll_id, "option": vote.option}


@app.put("/polls/{poll_id}/vote/")
async def update_vote(poll_id: str, vote: Vote):
    if poll_id not in polls_db:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Poll not found"})

    if vote.option not in polls_db[poll_id].options:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid option"})

    if poll_id not in votes_db or vote.user_id not in votes_db[poll_id]:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "User has not voted yet"})

    votes_db[poll_id][vote.user_id] = vote.option

    return {"message": "Vote updated", "poll_id": poll_id, "option": vote.option}


@app.delete("/polls/{poll_id}/vote/")
async def delete_vote(poll_id: str, vote: Vote):
    if poll_id not in polls_db:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Poll not found"})

    if vote.option not in polls_db[poll_id].options:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Invalid option"})

    if poll_id not in votes_db or vote.user_id not in votes_db[poll_id]:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "No vote found for this user"})

    del votes_db[poll_id][vote.user_id]

    return {"message": "Vote removed", "poll_id": poll_id}


@app.get("/polls/{poll_id}/results/")
async def get_poll_results(poll_id: str):
    if poll_id not in polls_db:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Poll not found"})

    vote_counts = {option: 0 for option in polls_db[poll_id].options}

    if poll_id not in votes_db or not votes_db[poll_id]:
        return {"poll_id": poll_id, "results": vote_counts}

    for user_id, selected_option in votes_db[poll_id].items():
        vote_counts[selected_option] += 1

    return {"poll_id": poll_id, "results": vote_counts}
