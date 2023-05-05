import React from "react";
import { useState, useEffect } from 'react'
import axios from 'axios';
import { useSelector } from "react-redux";
import { useDispatch } from "react-redux";
import { userlist } from "../Redux/action";
import { showuser } from "../Redux/action";
import { Navigate ,Link} from "react-router-dom";


const Userlist = () => {

  //requiring use selector and dispatch
  const dispatch = useDispatch()
  const data = useSelector(state => state)
  const [check, setCheck] = useState()
  const [id,setID] = useState('')
  const [Editid,setEditid] = useState('')
  const [Edit, setEdit] = useState('')

  useEffect(() => {
    axios({
      method: 'get',
      url: 'https://reqres.in/api/users?page=2'
    }).then((response) => {
      var values = response.data.data
      // setUser(response.data.data)
      dispatch(userlist(values))
    })
  }, [])

  function handleClick (e) {
    var id = e.target.id
    // console.log(id)
    setID(id)
    
    axios({
      method: 'get',
      url: `https://reqres.in/api/users/${id}`
    }).then((response) => {
      // console.log(response.data.data)
      dispatch(showuser(response.data.data))
      setCheck(true)
    })
  }

  const edit =(e)=>{
    console.log(e.target.id)
    setEditid(e.target.id)
    setEdit(true)

  }

  const dlt = (e)=>{
    console.log(e.target.id)
   
  }
  return (
    <>
      { check ? <Navigate to={`/showprofile/${id}`}/> :''}
      { Edit ? <Navigate to = {`/editprofile/${Editid}`}/>: ''}

      {console.log(data.users[0])}
      {/* {console.log(data.users[0])} */}
      {/* {console.log(data.showuser[0])} */} 

      {/* Displaying user names  */}
      <div class="container">
        <div class="row">
          <div class="col-lg-12">
            <div class="main-box clearfix">
              <div class="table-responsive">
                <table class="table user-list">
                  <thead>
                    <tr>
                      <th><span>Photo</span></th>
                      <th><span>ID</span></th>
                      <th><span>Email</span></th>
                      <th class="text-center"><span>First Name</span></th>
                      <th><span>Last Name</span></th>
                      <th><span>Action</span></th>
                      <th>&nbsp;</th>
                    </tr>
                  </thead>
                  <tbody>

                    {data.users.length>0 && data.users[0].map((data) => {
                      return (
                        <tr>
                          <td>
                            <img style={{ width: "45%" }} src={data.avatar} alt="" />
                            {/* <a href="#" class="user-link">Mila Kunis</a>
                          <span class="user-subhead">Admin</span> */}
                          </td>
                          <td>
                            <span class="label label-default">{data.id}</span>
                          </td>
                          <td>
                            <span class="label label-default">{data.email}</span>
                          </td>
                          <td>
                            <span class="label label-default">{data.first_name} </span>
                          </td>
                          <td>
                            <span class="label label-default">{data.last_name}</span>
                          </td>
                          <td >
                            <span class="fa-stack">
                              <i class="fa fa-square fa-stack-2x"  ></i>
                              <i class="fa fa-search-plus fa-stack-1x fa-inverse" onClick={handleClick} id={data.id}  ></i>
                            </span>

                              <span class="fa-stack">
                                <i class="fa fa-square fa-stack-2x"></i>
                                <i class="fa fa-pencil fa-stack-1x fa-inverse" onClick={edit} id={data.id}></i>
                              </span>
                              <span class="fa-stack">
                                <i class="fa fa-square fa-stack-2x"></i>
                                <i class="fa fa-trash-o fa-stack-1x fa-inverse" onClick={dlt} id={data.id}></i>
                              </span>
                          
                          </td>
                        </tr>
                      )
                    })}

                  </tbody>
                </table>
              </div>
              <ul class="pagination pull-right">
                <li><a href="#"><i class="fa fa-chevron-left"></i></a></li>
                <li><a href="#">1</a></li>
                <li><a href="#">2</a></li>
                <li><a href="#">3</a></li>
                <li><a href="#">4</a></li>
                <li><a href="#">5</a></li>
                <li><a href="#"><i class="fa fa-chevron-right"></i></a></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default Userlist