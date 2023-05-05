

export const userlist =(data)=>{
    return({
        type:"saveusers",
        payload:data
    })
    
}

export const showuser = (data)=>{
    return ({
        type:"showuser",
        payload:data
    })
   
}

export const updateid = (data)=>{
    return({
        type:"updateid",
        payload:data
    })
}