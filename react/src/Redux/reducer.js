import { showuser } from "./action"


const InitialState = {
    users:[],
    showuser:[],
    // id : 1
}

export const Reducer = (state=InitialState, action)=>{

    switch(action.type)
    {
        case "saveusers": return ({
            ...state,
            users:[...state.users,action.payload]
        })
        case 'showuser': return ({
            ...state,
            showuser:[...state.showuser,action.payload],
            // id : action.paylod.id
        })
        default: return ( InitialState )
    }

}



