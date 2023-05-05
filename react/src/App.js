
import Editprofile from './components/editprofie';
import { Routes, Route, BrowserRouter } from 'react-router-dom'
import Userlist from './components/userlist';
import Showprofile from './components/showprofile';
import Navbar from './components/navbar';




function App() {
  return (
   
  <>

    <BrowserRouter>
    <Navbar/>
      <Routes>
        <Route exact path='/' element={<Userlist />} />
        <Route path='/showprofile/:id' element={ <Showprofile  />}/>
        <Route path='/editprofile/:id' element={ <Editprofile  />}/>

      </Routes>
    </BrowserRouter>
  </>);
}

export default App;
