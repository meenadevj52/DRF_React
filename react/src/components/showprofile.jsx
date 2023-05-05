import React from "react";
import { useState, useEffect } from "react";
import { Link } from 'react-router-dom'
import { useSelector } from "react-redux";
import { useDispatch } from 'react-redux';
import {useParams} from "react-router-dom";
import { showuser } from '../Redux/action'
import axios from "axios";

const Showprofile = () => {

    const dispatch = useDispatch()
    const storedata = useSelector(state => state)
    const [data, setData] = useState([])
    const { id } = useParams()
    // console.log(id)

    useEffect(() => {
        axios({
            method: 'get',
            url: `https://reqres.in/api/users/${id}`
        }).then((response) => {
            // console.log(response.data.data)
            // dispatch(showuser(response.data.data))
            setData(response.data.data)
        })
    }, [])
    return (
        <>
            {/* {console.log(storedata)}     */}
            {/* {console.log(storedata.showuser[0])} */}
            < div class="container my-4 mx-4 emp-profile" >
                <form method="post">
                    <div class="row">
                        <div class="col-md-4">
                            <div class="profile-img">
                                <img src={data.avatar} alt="" />
                                <div class="file btn btn-lg btn-primary my-4">
                                    Change Photo
                                    <input type="file" name="file" />
                                </div>
                            </div>
                        </div>

                        <div class="col-md-6">
                            <div class="profile-head">
                                <h5>
                                    {data.first_name} {data.last_name}
                                </h5>
                                <h6>
                                    Web Developer and Designer
                                </h6>
                                <p class="proile-rating">{data.email}</p>

                            </div>
                        </div>

                        <div class="col-md-2">
                            <Link to={``} class="profile-edit-btn" name="btnAddMore"> Delete profile </Link>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-4 mx-6">
                            <div class="profile-work">
                                <p>WORK LINK</p>
                                <a href="">Website Link</a><br />
                                <a href="">Bootsnipp Profile</a><br />
                                <a href="">Bootply Profile</a>
                                <p>SKILLS</p>
                                <a href="">Web Designer</a><br />
                                <a href="">Web Developer</a><br />
                                <a href="">WordPress</a><br />
                                <a href="">WooCommerce</a><br />
                                <a href="">PHP, .Net</a><br />
                            </div>
                        </div>



                        <div class="col-md-8">
                            <div class="tab-content profile-tab" id="myTabContent">
                                <div class="tab-pane fade show active" id="home" role="tabpanel" aria-labelledby="home-tab">

                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>User Id</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>Kshiti123</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>Name</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>Kshiti Ghelani</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>Email</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>kshitighelani@gmail.com</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>Phone</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>123 456 7890</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>Profession</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>Web Developer and Designer</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="tab-pane fade" id="profile" role="tabpanel" aria-labelledby="profile-tab">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>Experience</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>Expert</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>Hourly Rate</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>10$/hr</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>Total Projects</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>230</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>English Level</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>Expert</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label>Availability</label>
                                        </div>
                                        <div class="col-md-6">
                                            <p>6 months</p>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-12">
                                            <label>Your Bio</label><br />
                                            <p>Your detail description</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </form>

            </div>

        </>
    )
}
export default Showprofile